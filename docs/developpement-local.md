# Développement et vérification en local

Les étapes 1 à 5 fournissent Next.js, FastAPI, PostgreSQL/pgvector,
l’authentification par `prenom.nom` / mot de passe, l’import privé, l’extraction,
l’indexation E5 et la recherche privée inspectable.
Aucun déploiement ni provisionnement cloud.
[Parcours, limites et reprise de l’import](etape-3-import-local.md).

## Lancer le socle

Prérequis : Ubuntu/WSL, Python 3 pour le script de configuration, Docker et Docker
Compose v2. Node et les dépendances Python sont fournis par les images.

```bash
cd /home/daniel/assistant-rag
python3 scripts/local/bootstrap.py
docker compose build backend frontend
docker compose build worker
python3 scripts/local/prepare_embeddings.py --download
docker compose up -d --wait
```

- Application : http://localhost:3000
- API : http://localhost:8000/health
- Documentation API : http://localhost:8000/docs
- PostgreSQL : `localhost:5433`, base/utilisateur `assistant_rag`.

Les ports sont modifiables dans `.env` avant le lancement. Tous les ports Docker
sont publiés sur `127.0.0.1`. Les conteneurs appartiennent au projet Compose
`assistant-rag`, indépendant des autres projets de la machine.

Le script crée ou complète `.env` : mot de passe PostgreSQL, secrets Better Auth
local/test et origine `BETTER_AUTH_URL`, avec permissions `0600`. Les valeurs
existantes non vides sont conservées ; les champs vides d’un `.env.example` copié sont complétés. Si le port frontend change, adapter aussi cette origine. `.env.local`, qui contient la clé
Groq du prototype, n'est ni lu ni modifié. Les secrets sont ignorés par Git et
exclus des contextes de construction Docker. Aucune clé LLM n'est requise ici.
Les identifiants PostgreSQL locaux ne servent pas à la production.

Compose attend que PostgreSQL soit prêt, applique `alembic upgrade head`, puis
démarre l’API, le worker d’ingestion et Next.js. Les sources sont montées pour le rechargement local.
Les dépendances et le cache Next.js sont dans des volumes dédiés. Les versions
des dépendances sont verrouillées ; les images applicatives et pgvector ont un
digest fixé. Les Dockerfile de ce socle servent au développement local.

## Contrôler le fonctionnement

Le bouton « Vérifier la connexion » appelle `/api/v1/health` sur la même origine.
Next.js relaie cette route vers FastAPI grâce à `API_INTERNAL_URL`, une variable
serveur absente du bundle navigateur. Un Route Handler relaie les routes métier
après vérification de session et émission serveur d’un JWT pour FastAPI.
`/api/auth/*` utilise le SDK Better Auth, avec une liste réduite de routes exposées.
Aucun CORS permissif n’est nécessaire.

`GET /health` vérifie que l'API répond. `GET /api/v1/health` renvoie `200` avec
`{"status":"ok"}` uniquement si PostgreSQL est joignable, pgvector activé et
la migration attendue appliquée. Sinon, il renvoie `503` et
`{"status":"unavailable"}`. Réponses non mises en cache, sans URL de base,
identifiant, version d'infrastructure ou message brut d'exception.

```bash
bash scripts/local/check.sh
```

Cette commande exécute : Ruff, mypy, les tests API, les tests de migrations et de
recherche vectorielle, ESLint, TypeScript strict, une compilation de production,
les parcours Chromium sur bureau/mobile, puis une vérification de persistance.
La compilation utilise `.next-build` pour conserver le serveur de développement.
Playwright utilise un conteneur local, sans installation de navigateur sur l’hôte.
Son frontend `frontend-auth-test` utilise le build de production `.next-build`,
pour éviter les compilations à la demande pendant les essais. Les serveurs
`frontend-auth-test` et `backend-auth-test` ont une base et un secret
séparés, sans ports publiés. Ils sont arrêtés avant toute remise à zéro du schéma
et après les essais. Un seul worker Playwright évite la concurrence avec les compteurs partagés.
Le service `worker-auth-test` consomme les imports de test sur un stockage distinct.

Pour relancer uniquement le navigateur, après compilation et préparation de la base de test :

```bash
docker compose --profile test stop frontend-auth-test backend-auth-test worker-auth-test llm-test
docker compose exec -T backend python scripts/test_database.py
docker compose run --rm --no-deps -e NEXT_DIST_DIR=.next-build frontend npm run build
docker compose --profile test run --rm e2e
docker compose --profile test stop frontend-auth-test backend-auth-test worker-auth-test llm-test
```

La préparation efface uniquement le schéma de la base de test. Les comptes
créés par les essais n’apparaissent pas dans l’application locale principale.

Les tests de base et d’identité utilisent exclusivement `assistant_rag_test` dans PostgreSQL
local. Ils recréent son schéma `public` ; aucune donnée de `assistant_rag` n'est
effacée. La vérification de persistance crée un vecteur synthétique de 384
dimensions dans cette base de test, recrée seulement le conteneur `db` de ce
projet en conservant son volume, contrôle le vecteur, puis nettoie sa fixture.
Ce contrôle interrompt brièvement la connexion locale à PostgreSQL.
Le contrôle supplémentaire `verify_import_persistence.py` compare les empreintes
des originaux et des unités de test avant/après recréation de l’API et du worker,
sans afficher de texte privé. Les volumes de fichiers principaux ne sont pas touchés.

Pour n'exécuter que les tests Python :

```bash
docker compose exec -T backend pytest -q -m 'not integration'
docker compose exec -T backend python scripts/test_database.py
```

Pour voir les états ou les logs :

```bash
docker compose ps -a
docker compose logs --tail=50 frontend backend worker migrate
```

Ne pas partager `docker compose config` sans filtrage : sa sortie complète
contient les variables résolues. Utiliser `docker compose config --quiet` pour
valider la configuration sans afficher les secrets.

## Persistance et migrations

Les volumes `assistant-rag_private_files` et `assistant-rag_postgres_data`
conservent les originaux privés et PostgreSQL quand les conteneurs
sont arrêtés ou recréés. `docker compose down` conserve les données ; l'option
`--volumes` les supprime et ne fait pas partie du lancement ou des contrôles.

```bash
docker compose stop
docker compose up -d --wait
docker compose exec -T backend alembic current
docker compose exec -T backend alembic upgrade head
```

La migration `0001_vector` active l’extension. `0002_identity` crée les tables
Better Auth et `users` (UUID, identité SDK unique et clé étrangère). `0003_documents` ajoute les documents, unités extraites et travaux durables ;
`0004_indexes` ajoute les passages, générations et vecteurs ;
`0005_search` ajoute la file éphémère des questions ; `0006_generation` les quotas
partagés ; `0007_conversations` l’historique privé et les citations effaçables. À chaque nouvelle migration,
mettre à jour la révision compatible dans `app/repositories/health.py` et tester
le démarrage. Une réapplication ne supprime ni les données ni l'extension.

Un retour à `base` supprime pgvector seulement si aucune colonne n'en dépend :
il n'utilise jamais `CASCADE`. Il est testé sur une base isolée vide. Les futures
migrations de données devront documenter leurs propres sauvegardes et retours
arrière ; ce contrôle initial n'atteste pas leur réversibilité.

## Cadence Vercel et budget

Les développements et validations courants restent locaux. Une qualification
Vercel sera regroupée à un jalon ultérieur lorsque le projet aura suffisamment
avancé et que le porteur souhaitera préparer ce déploiement. L'application V1
devra toujours être authentifiée et hébergée publiquement sur Vercel.

Neon Free, les origines publiques Better Auth, Blob et Queues seront provisionnés et
qualifiés à ce jalon selon les composants disponibles. Les étapes locales
utiliseront des adaptateurs locaux lorsque leur intégration sera nécessaire.
`vercel.json` décrit encore le prototype de l'étape 0 et sera adapté à ce moment.
Aucun hook, script ou workflow du socle ne déploie automatiquement.

Le lancement et les tests n'appellent aucun LLM ni service payant. Le budget de
0 € et les critères de suspension au quota d'ADR 0002 restent applicables.

## Comptes locaux

Ouvrir `/sign-up`, choisir `prenom.nom` (sans accents, chiffres/traits d’union
acceptés) et un mot de passe de 12 à 128 caractères. La connexion est `/sign-in`,
l’espace privé `/library`. Aucun e-mail, fournisseur externe ou clé OAuth requis.

Le secret `BETTER_AUTH_SECRET` est une valeur serveur, distincte de
`TEST_AUTH_SECRET` ; conserver le premier avec la base locale. Le changer
invalide les cookies et rend les clés privées JWT existantes indéchiffrables.
Ne pas le remplacer en gardant les tables d’authentification sans procédure de
rotation adaptée. Ces valeurs ne doivent jamais être copiées dans la production.

Sessions de 7 jours, déconnexion immédiate, origines POST exactes. L’HTTP local
n’utilise pas l’attribut Secure ; l’HTTPS l’active. Limites globales locales :
5 inscriptions et 10 connexions par minute. Le formulaire indique un refus temporaire.
Aucune récupération automatique de mot de passe en V1 ; voir [ADR 0003](decisions/0003-identifiants-locaux.md).

L’ajout de dépendances nécessite de reconstruire l’image **et** de synchroniser
le volume de modules existant, avant les essais :

```bash
docker compose stop frontend
docker compose build frontend
docker compose run --rm --no-deps frontend npm ci --no-audit --no-fund
docker compose up -d --wait
```

Ne pas lancer plusieurs installations sur le même volume. Le script
`frontend/scripts/auth-schema.ts` compile un brouillon SQL à relire ; il ne
modifie pas une migration existante et ne migre pas la base. Toute évolution
ultérieure passe par une nouvelle révision Alembic et des essais isolés.

## Découpage et indexation : étape 4

La suite `bash scripts/local/check.sh` arrête temporairement le frontend de
développement et son worker pendant le build et les tests navigateur. Elle les
relance à sa sortie, y compris en cas d’échec, sans supprimer les volumes. Cette
exécution séquentielle garde un seul frontend et un seul modèle E5 en mémoire.

Le modèle E5 public figé est préparé dans `.models/e5`, exclu des fichiers suivis.
`prepare_embeddings.py --download` réutilise le cache Hugging Face existant ou
récupère gratuitement la révision publique, sans clé API. Il copie les fichiers
avec leurs SHA-256. Le modèle reste en mémoire entre lots dans un processus CPU
isolé, avec démarrage borné à 90 secondes et calcul borné à 45 secondes. Sans `--download`, un cache absent provoque une erreur et
aucun accès réseau. Cette préparation se fait après la construction du worker.
Le téléchargement initial fait environ 470 Mio ; prévoir aussi l’espace disque
pour l’image CPU PyTorch. Il ne s’agit pas d’un abonnement ni d’un service cloud.

L’ordre de construction est explicite : backend/frontend, puis worker. Le worker
hérite de l’image API locale et ajoute les dépendances CPU exactes du lock séparé.
Next.js et FastAPI ne chargent pas le modèle. Compose monte `.models/e5` en lecture
seule ; le worker vérifie le manifeste et fonctionne hors ligne. Les originaux
restent dans leur volume privé distinct, protégé comme à l’étape 3.

L’import déclenche désormais le découpage et l’indexation, puis l’état `ready`.
La progression indique les passages enregistrés. « Voir le texte » conserve la
vue d’extraction ; « Voir les passages » ouvre le texte exact et ses repères.
Après trois erreurs consécutives, « Relancer » reprend les checkpoints conservés.

```bash
# Mesure CPU seule, sans build ni navigateur simultané.
docker compose stop worker
python3 scripts/local/qualify_indexation.py
docker compose up -d worker

# Après les tests navigateur, uniquement sur assistant_rag_test.
python3 scripts/local/verify_index_persistence.py
```

`check.sh` inclut désormais la persistance des passages/vecteurs, en plus du test
PostgreSQL. Les rapports de l’étape 3 restent des preuves historiques ; son ancien
script de persistance ciblait l’état intermédiaire avant indexation.
Voir [paramètres, résultats et limites](etape-4-indexation-locale.md) et
[ADR 0005](decisions/0005-indexation-locale-reprenable.md).

La migration additive `0004_indexes` conserve les comptes, les originaux et les
unités, puis met les extractions existantes en file. Une sauvegarde PostgreSQL
locale avant application est conservée dans `evaluation/.qa/`, avec permissions
privées ; ne pas la publier. Pour une autre installation, exporter la base avec
`pg_dump -Fc` et sauvegarder les originaux ensemble avant migration. Le downgrade
0004 détruit les index et impose un retour de code coordonné ; il est testé
exclusivement sur la base isolée, jamais sur les données principales.

## Recherche privée : étape 5

Depuis `/library`, ouvrir « Rechercher dans mes documents » ou aller sur
[la recherche locale](http://localhost:3000/search). Une question retrouve jusqu’à
cinq passages avec texte exact, fichier, repères et score. On peut choisir une
sélection explicite ; seuls les documents prêts du compte sont consultés.
Cette étape ne génère pas encore de réponse ni d’historique de conversation.

La recherche utilise la distance cosinus exacte et le modèle E5 résident du
worker. Une file PostgreSQL privée borne les questions et le nombre de travaux.
Le verrou CPU est détenu sur une connexion PostgreSQL pendant chaque cycle :
une annulation ou une déconnexion ne permet pas un deuxième calcul simultané.
Les résultats d’un travail annulé/révoqué ne sont pas publiés. Aucun document,
extrait ou question n’est envoyé à Groq ni à un service d’embeddings.

```bash
# Calibration sur les vingt cas de développement, sans toucher au lot final.
python3 scripts/local/qualify_retrieval.py

# Après les tests navigateur, sur la base assistant_rag_test uniquement.
python3 scripts/local/verify_search_persistence.py
```

Le premier script réimporte les fixtures et exécute le pipeline réel dans
`assistant_rag_evaluation` avec son propre stockage privé local. Il mesure E5 et
SQL à chaud, sans inclure le navigateur. Le second contrôle les originaux,
unités, vecteurs et résultats exacts après remplacement des services ; il reste disponible comme contrôle historique. `check.sh` utilise désormais
le contrôle combiné de l’étape 7. Les preuves des étapes précédentes restent conservées.

`SEARCH_THRESHOLD` est un réglage serveur optionnel, **0,84** par défaut. Si on
l’ajoute à une autre installation, transmettre cette variable au backend et
recalibrer uniquement sur le lot de développement. Les dix cas finaux restent
réservés à la V1. [Méthode, résultats et limites](etape-5-recherche-locale.md) ·
[ADR 0006](decisions/0006-recherche-privee-et-seuil.md).

La migration additive `0005_search` conserve les comptes et les index. Avant son
application sur une installation existante, exporter PostgreSQL avec `pg_dump -Fc`
et sauvegarder les originaux privés ensemble. Son downgrade supprime la file
éphémère et exige de remettre le code de l’étape 4 ; les essais de rollback se
font sur la base isolée, jamais sur les documents de développement.

## Réponses sourcées : étape 6

La recherche locale reste disponible sans clé. Pour la génération Groq Free,
placer la clé dans `.env.local`, confirmer que le compte affiche Free, puis :

```bash
python3 scripts/local/configure_llm.py --free-confirmed
docker compose up -d --no-deps --force-recreate backend
```

Le script copie uniquement la clé Groq dans `.secrets/groq_api_key` (`0600`,
dossier `0700`) et confirme le mode Free dans `.env`. Les identifiants existants
et `.env.local` restent conservés. Le montage est réservé au backend : aucune
clé réelle dans Next.js, les workers, les migrations ou les tests. L’image du
backend cache aussi le vocabulaire public du tokenizer GPT-OSS à sa construction.

Depuis `/search`, choisir les documents et accepter l’envoi à Groq pour générer
une réponse. Les citations ouvrent la preuve textuelle et le passage privé.
Cette page reste ponctuelle ; les échanges sont enregistrés dans `/conversations`
depuis l’étape 7.
Pour des documents personnels, activer Zero Data Retention dans le compte Groq.

`check.sh` utilise le seul fournisseur HTTP synthétique du profil de test et
vérifie la persistance des documents, vecteurs, recherches et compteurs. Il ne
consomme pas Groq. La qualification réelle est séparée et explicitement bornée :

```bash
python3 scripts/local/qualify_answers.py --real --revalidate-retained
```

Le journal du volume d’évaluation conserve les seules réponses de fixtures
publiques pour les revalider sans nouvel appel. Le script distingue réutilisation
et appels réels ; il ne touche jamais au lot final. Les compteurs de l’application
sont partagés dans PostgreSQL : chaque tentative, même échouée, réserve 3 100
tokens ; 10/jour/compte, 50 globalement et 2/minute, une génération simultanée.
Les quotas atteints interrompent l’action sans bascule payante.

Migration `0006_generation`, précédée d’une sauvegarde privée ; downgrade réservé
aux essais isolés, car il détruit les compteurs et exige le code de l’étape 5.
[Résultats et limites de complétude](etape-6-reponses-locales.md) ·
[Choix techniques](decisions/0007-generation-sources-et-quotas.md).

## Conversations et historique : étape 7

Ouvrir [mes conversations](http://localhost:3000/conversations) depuis la
bibliothèque. Créer un échange, choisir ses documents et accepter l’envoi du
contexte utile à Groq avant chaque question. Rechargement et reconnexion relisent
les réponses enregistrées sans appel fournisseur. Les suivis utilisent l’historique
serveur borné, puis relancent la recherche privée.

Une question échouée reste visible, sans fausse réponse. Un envoi réseau répété
avec le même UUID retrouve son état ; le serveur sérialise les échanges. La
suppression d’un document retire les extraits de ses citations historiques.
Les textes des questions/réponses restent jusqu’à suppression de la conversation.
Limites gratuites locales : 50 conversations par compte et 100 échanges chacune.

`check.sh` termine avec `verify_conversation_persistence.py`, sur la seule base
et les fichiers de test. Il compare originaux, index, recherche, quotas, échanges
et sources disponibles/supprimées après recréation PostgreSQL/API/worker. Les
rapports des étapes 3 à 6 restent conservés, sans réécriture. Le fournisseur
simulé est isolé ; aucun nouvel appel Groq réel n’est requis.

La migration additive `0007_conversations` conserve les tables précédentes.
Sauvegarde privée avant application. Un downgrade vers `0006_generation` efface
les conversations et leurs citations : le tester uniquement sur la base isolée,
avec un retour de code coordonné. [Parcours et preuves](etape-7-conversations-locales.md) ·
[ADR 0008](decisions/0008-conversations-privees-et-reprise.md).


## Essais OpenAI locaux — 14 octobre 2026

Groq reste le modèle initial. Placer la clé seule, sur une ligne, dans
`/home/daniel/assistant-rag/.secrets/openai_api_key` (permissions 600).
Le dossier `.secrets` est déjà exclu de Git et monté uniquement dans le backend.
Après mise à jour du code, appliquer `docker compose run --rm migrate`, puis
`docker compose up -d backend frontend worker`. Une clé ajoutée ensuite est lue
sans redémarrage : actualiser la page. Le sélecteur affiche les deux modèles
OpenAI et le budget prudent restant lorsqu’un modèle OpenAI est sélectionné.

Migration `0009_openai_trial`, compteur global persistant de 1 USD et arrêt avant
tout appel dépassant ce plafond. Réserve par tentative : 0,01 USD Luna, 0,12 USD
Sol, conservée même en cas d’échec. Ne pas confondre ce compteur avec la facture.
Aucun changement Vercel. [Décision et rollback](decisions/0011-openai-local-plafond-un-dollar.md).


Correctif OpenAI : appliquer aussi `0010_generation_token_capacity`, qui autorise
la réservation de tokens OpenAI dans le compteur journalier historique. Après
migration, relancer le backend. Les plafonds de dépenses restent inchangés.


### OpenAI après transfert en production

Le porteur a autorisé le transfert du budget restant vers Vercel. Le backend
Compose garde désormais `OPENAI_LOCAL_ENABLED=false` et le compteur local est
verrouillé à son plafond. Les instructions d’essais locaux précédentes constituent
l’historique ; ne pas réactiver ou remettre à zéro ce compteur. Groq reste utilisable
localement. Voir ADR 0011 pour l’activation et le journal de production.
