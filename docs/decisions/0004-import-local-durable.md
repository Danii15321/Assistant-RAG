# ADR 0004 — Import privé et extraction durable en local

- Date : 11 octobre 2026
- Statut : accepté dans le périmètre local de l’étape 3
- Contrainte : budget de 0 €, sans déploiement ni provisionnement cloud

## Décision

Les fichiers sont envoyés directement du navigateur à FastAPI local, après une
réservation authentifiée. Next.js ne relaie que les petits messages JSON et ne
reçoit pas les octets du fichier. L’adaptateur local stocke des objets privés dans
un volume Docker, avec une clé UUID attribuée par le serveur.

Une autorisation aléatoire de 256 bits, conservée uniquement sous forme de SHA-256
dans PostgreSQL, est limitée à une réservation, sa taille, son type et dix minutes.
Elle est liée à la session active et consommée à la publication de l’objet.
L’URL ne contient aucun jeton. Le JWT Better Auth reste exclusivement côté serveur.
L’envoi vérifie l’origine exacte et la session avant réception et publication.

La finalisation vérifie les octets réellement stockés, calcule SHA-256 et applique
la déduplication par propriétaire. Sa transaction publie aussi un travail durable
dans `ingestion_jobs`. Cette table est à la fois l’outbox et la file de l’adaptateur
local : aucune publication réseau intermédiaire ne peut perdre l’événement.
Le worker indépendant consomme ces travaux et persiste les résultats atomiquement.

Un seul travail tourne à la fois, grâce à un verrou PostgreSQL et un bail de
60 secondes. Un jeton de bail distinct empêche un ancien consommateur de publier
après reprise. Trois tentatives au maximum pour l’extraction ; les erreurs
permanentes échouent immédiatement. Le nettoyage reste reprenable après une panne.

## État intermédiaire avant l’indexation

L’extraction réussie conserve `state=processing`, `stage=extracted`, une version
et des unités localisées. L’interface affiche **Texte extrait**. Aucun travail ne
reste actif et aucun document n’est encore recherchable. `ready` reste réservé à
la publication complète de l’index à l’étape 4. Cela évite de prétendre qu’un texte
simplement extrait possède déjà des vecteurs utilisables.

## Parseurs et limites

[pypdf 6.19.0](https://pypi.org/project/pypdf/6.19.0/) est une bibliothèque Python
sous licence BSD-3-Clause. Le DOCX est lu comme un conteneur ZIP/XML, sans extraction
sur disque, avec [defusedxml 0.7.1](https://github.com/tiran/defusedxml), sous licence
PSF. Les entités et DTD sont interdites. Aucun moteur Word ou OCR n’est nécessaire.
Les deux dépendances sont verrouillées ; le parseur s’exécute dans un sous-processus
sans journalisation du contenu, avec mémoire, CPU et durée bornés.

## Suite au jalon Vercel

Le disque local et le worker permanent sont réservés au développement Docker.
Le jalon cloud devra remplacer l’adaptateur par Blob privé et un upload direct
Blob autorisé, puis relier l’outbox à Queues avec publication/réconciliation fiables
et consommation authentifiée dans une invocation Python bornée. Les services
métier et la persistance des états peuvent être réutilisés. Les offres gratuites
et le comportement réel restent à qualifier ensemble avant publication.
