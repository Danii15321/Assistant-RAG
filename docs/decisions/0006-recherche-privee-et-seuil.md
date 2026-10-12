# ADR 0006 — Recherche privée exacte et calibration de développement

- Date : 11 octobre 2026.
- Statut : acceptée et qualifiée en local ; qualification cloud différée.
- Références : [spécification](../specification.md), [ADR 0005](0005-indexation-locale-reprenable.md).

## Contexte

L’étape 5 doit retrouver des passages du compte connecté, avec sélection,
scores et repères vérifiables. Le budget reste de 0 €. L’encodage E5 occupe
environ 1 Gio : charger un second modèle dans FastAPI augmenterait inutilement
la consommation de la machine WSL partagée.

## Décision

Faire la recherche exacte dans PostgreSQL avec la distance cosinus pgvector.
Un CTE matérialisé filtre propriétaire, génération publiée, version compatible,
état `ready` et sélection avant le classement. Ne pas créer d’index approximatif
à ce stade. La sélection explicite est revalidée sous verrou partagé dans la
transaction de classement ; une suppression ou une réindexation ne peut pas
transformer une sélection invalide en recherche générale.

Réutiliser le processus E5 du worker pour les questions, avec `query: ` et L2,
le même modèle/révision/dimension que les passages. Une file éphémère privée dans
PostgreSQL transmet la question et son embedding à l’API. Elle vérifie session
et propriétaire, limite un travail par compte et huit globalement, et partage
le verrou CPU des travaux d’ingestion. Un verrou de session PostgreSQL reste
détenu pendant le calcul, même après annulation du travail ou suppression de sa
session ; il est libéré avant restitution de la connexion au pool.
Alterner recherche et ingestion pour que
des recherches répétées ne bloquent pas les imports.

Les questions sont limitées à 1 000 caractères. Les quatre messages historiques
autorisés sont bornés à 500 caractères chacun ; seules les deux dernières
questions utilisateur aident la recherche des suivis. Les réponses assistant ne
deviennent jamais une preuve. Le tokenizer refuse plus de 512 tokens avec
préfixe/tokens spéciaux ; aucune troncature silencieuse.

Par défaut : 50 candidats, top-k 5, maximum 10 demandé et 1 500 tokens de contexte.
Retirer les textes identiques après normalisation des espaces et les passages
d’une même génération dont le chevauchement représente au moins 80 % du plus
court. Conserver le texte exact des passages retenus.

Seuil retenu : **0,84**, calibré exclusivement sur les 20 cas `development`.
Comparer une grille de 0,65 à 1 par pas de 0,005. Parmi les seuils avec Recall@5
≥ 80 %, maximiser les rejets hors corpus, puis le rappel, puis le seuil.
Les dix cas `final` restent réservés à la qualification de la V1.

## Conséquences

La recherche renvoie des passages et leurs scores, sans génération ni appel
Groq. L’interface permet d’ouvrir le texte, de choisir les documents et de gérer
les erreurs, le corpus vide et l’absence de correspondance.

Le score de similarité n’est pas une probabilité ni une validation de réponse.
Le Recall@5 de développement est de 82,4 % sur 17 questions répondables ;
17 annotations pertinentes sur 20 sont couvertes. Le seuil rejette seulement
une des trois questions hors corpus. La génération de l’étape 6 devra encore
vérifier l’information disponible et s’abstenir lorsque la réponse manque.

Les recherches ne créent pas d’historique persistant. La question est effacée
après calcul et le travail après consommation ; expiration à 130 secondes,
purge au cycle du worker ou à sa reprise. Les erreurs techniques restent des
erreurs HTTP, jamais une abstention réussie. Les services cloud, le routage de
file, la concurrence et les performances publiques restent au jalon Vercel.
