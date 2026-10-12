# ADR 0008 — Conversations privées et reprise des échanges

- Date : 12 octobre 2026.
- Statut : acceptée et qualifiée en local.
- Références : [spécification](../specification.md), [génération](0007-generation-sources-et-quotas.md).

## Décision

Ajouter des conversations privées dans PostgreSQL et les pages `/conversations`
et `/conversations/{id}`. Le titre vient des 80 premiers caractères de la première
question, sans appel LLM. La bibliothèque et la recherche ponctuelle restent
accessibles ; seuls les envois dans une conversation sont enregistrés.

Un échange stocke question, sélection (`null` = tous les documents prêts), ordre,
UUID client, dates, état et réponse éventuelle. Il représente le message utilisateur
et, en cas de réussite ou d’abstention, le message assistant. Une erreur technique
conserve la question avec `failed` et un code stable, sans texte documentaire.
Le client ne fournit aucun historique : celui-ci est relu côté serveur.

Lire au plus trois échanges terminés, soit six messages bornés à 500 caractères.
Seules les deux dernières questions utilisateur contextualisent la recherche et
le prompt existants. Les réponses antérieures ne deviennent jamais des preuves.
Chaque suivi relance E5 et la recherche SQL filtrée ; la sélection est celle du
nouvel échange, sans élargissement silencieux si elle est indisponible.

Un verrou de ligne alloue l’ordre et un bail de 210 secondes par conversation.
L’UUID d’échange sert de jeton : un travail expiré ne peut pas publier ni libérer
le bail suivant. Une autre question reçoit `409 conversation_busy`. Une répétition
du même UUID client et du même contenu retourne l’échange existant : `202` s’il
est en cours, sinon `200`, sans recherche ni appel supplémentaires. Changer le
contenu sous cet UUID est un conflit. Un échec reste un échec sous cet UUID ; une
nouvelle tentative explicite utilise un nouvel UUID. Après perte réseau, le client
relit l’historique et, si nécessaire, propose de vérifier le même envoi. Après récupération, vider la question et
réinitialiser l’accord, en conservant la sélection documentaire.

Les baux expirés sont transformés en échecs à la prochaine lecture/envoi.
Aucune reprise automatique du fournisseur n’est lancée. La suppression d’une
conversation annule la publication en cours et efface échanges/citations par
cascade. Elle n’efface pas les compteurs Groq de l’étape 6.

## Suppression des sources

Les citations ont une table distincte avec clé étrangère document/propriétaire.
La réponse conserve les textes des affirmations et des indices de citations,
mais aucun extrait cité. Les passages et citations exactes vivent uniquement dans
les snapshots de sources. Un trigger retire ces deux textes dès l’exclusion
`deleting`, et également avant une suppression SQL physique. Le repère et le nom
restent accompagnés de « Source supprimée ». L’API restitue alors des citations
vides, sans texte documentaire ; elle ne récupère pas le fichier supprimé.

À la publication, vérifier les passages exacts sous verrou partagé du document
**dans la transaction qui enregistre la réponse**. Une suppression concurrente
arrive donc avant la vérification (réponse refusée), ou après la publication
(snapshots immédiatement nettoyés). Les clés étrangères composites imposent le
même propriétaire entre conversation, échange et source.

Les textes des anciennes questions et réponses restent dans l’historique et
peuvent contenir des informations du document supprimé. L’interface explique
qu’il faut supprimer aussi la conversation pour effacer ces textes. Les exports
ou sauvegardes déjà réalisés ne sont pas réécrits par une suppression applicative.

## Budget et limites

Aucune nouvelle dépendance ni service. Limites locales : 50 conversations par
compte, 100 échanges par conversation, question de 1 000 caractères et sélection
de 50 documents. La création est sérialisée sur le propriétaire pour appliquer
le quota atomiquement. Les listes API sont paginées ; l’interface charge ces
listes bornées. Les réponses et citations ne sont pas stockées dans le navigateur.

La suite ordinaire garde le fournisseur HTTP synthétique isolé, avec E5 CPU réel
pour le navigateur. Elle ne possède pas la clé Groq réelle. Le suivi Q28 du lot
de développement vérifie la contextualisation côté serveur, sans évaluer la
qualité du modèle Groq. Les dix cas finaux restent réservés à l’étape 8.

## Migration et retour arrière

`0007_conversations` est additive : trois tables, index et triggers. Une sauvegarde
locale privée `evaluation/.qa/stage7-before-migration.dump` précède l’application.
Les comptes, documents, index et compteurs existants sont conservés. Les copies
et volumes restent privés, exclus des artefacts à publier.

Le downgrade vers `0006_generation` retire uniquement conversations/sources et
leurs triggers, avec perte de cet historique. Il exige le code de l’étape 6 ;
il ne remet pas les quotas à zéro. Le tester sur la base isolée seulement.
Pour restaurer réellement un historique, utiliser un export cohérent base/fichiers
sur une cible isolée, puis vérifier avant bascule. Aucun rollback principal ni
nouveau déploiement Vercel ne fait partie de cette étape.
