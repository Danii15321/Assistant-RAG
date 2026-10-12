# ADR 0005 — Indexation locale, versionnée et reprenable

- Date : 11 octobre 2026.
- Statut : accepté pour l’étape 4 locale.
- Références : [spécification](../specification.md), [import durable](0004-import-local-durable.md).

## Contexte

L’étape 3 conserve les originaux privés et leurs unités textuelles localisables.
L’étape 4 doit les indexer sans coût, sans publication cloud et sans rendre une
indexation partielle consultable. La base et les travaux doivent survivre au
remplacement du consommateur.

## Décision

Utiliser E5 small sur CPU, avec les versions de dépendances qualifiées à l’étape 0.
La révision du modèle est `614241f622f53c4eeff9890bdc4f31cfecc418b3`, la dimension
384, les préfixes `passage: ` / `query: ` et une normalisation L2.
Le modèle public est préparé une fois, vérifié par empreinte et monté en lecture
seule. Le traitement des documents fonctionne hors ligne. L’API et Next.js ne
chargent ni les poids ni PyTorch.

Le texte canonique du document concatène les unités dans leur ordre d’extraction,
avec deux sauts de ligne entre unités. Les passages sont des tranches exactes de
cette chaîne, avec offsets de caractères, ordres d’unités et repères physiques
de début/fin. Le tokenizer E5 fixe le budget de 300 tokens et le chevauchement
de 50 tokens. Les frontières de paragraphe et de phrase sont privilégiées dans
la seconde moitié du budget ; aucune reconstruction du texte par décodage.

La migration additive `0004_indexes` introduit un manifeste de génération et
les passages avec leurs vecteurs facultatifs. Les documents déjà extraits sont
mis en file. L’extraction et la création du travail d’indexation sont atomiques.
Les FK composées imposent la cohérence document/propriétaire/génération.

La réservation des passages est sérialisée dans PostgreSQL : 10 000 par compte,
20 000 au total, indexations en cours ou échouées comprises. Une génération
préparée réserve son quota complet ; une relance ne le réserve pas une seconde
fois. Les réservations sont libérées par la suppression effective du document.

Chaque travail calcule au maximum 16 embeddings dans un processus CPU borné à
45 secondes, après un démarrage du modèle borné à 90 secondes. Le processus
CPU conserve le modèle entre lots ; il est tué et recréé en cas d’erreur. Le bail
d’indexation de 120 secondes et son jeton excluent un producteur expiré.
Chaque lot enregistré libère le bail et réarme le travail, avec un checkpoint
persistant. Trois échecs consécutifs terminent le travail ; une relance manuelle
reprend les passages manquants. Les lots réussis réinitialisent ce compteur.

Le dernier lot publie simultanément les vecteurs, les compteurs et l’état `ready`.
La consultation des passages impose propriétaire, génération courante, version
compatible et document prêt dans SQL. Une suppression retire immédiatement le
document et empêche tout résultat en vol de le republier.

## Conséquences

- Le modèle reste en mémoire dans un processus CPU isolé. Le chargement intervient
  au premier lot ou après une interruption ; les lots suivants évitent ce coût.
  La mémoire reste bornée par le conteneur et les calculs par leur timeout.
- L’image du worker est séparée de l’API et limitée à 1,5 Gio en local.
- Une incompatibilité de configuration bloque la reprise ; aucun mélange de
  versions ni basculement vers un fournisseur payant.
- La consultation des passages est disponible ; la recherche et son évaluation
  restent l’étape 5. Aucun seuil n’est réglé sur les questions de validation.
- Vercel, Blob, Neon et Queues restent à qualifier au jalon regroupé demandé
  par le porteur ; le worker permanent actuel est un adaptateur local.
