## My Talking RAG — Faites parler vos documents

## OBJECTIF
Construire un assistant permettant à un utilisateur d’importer ses propres documents et de poser des questions dont les réponses s’appuient sur leur contenu
### Exemple :
Un étudiant importe ses cours, ses supports PDF et ses notes. L’assistant peut ensuite répondre à des questions précises et indiquer les passages utilisés

## FONCTIONNALITÉS À DÉVELOPPER
- Import de fichiers PDF, DOCX et TXT
- Extraction et découpage des documents
- Génération d’embeddings et indexation vectorielle
- Recherche sémantique des passages pertinents
- Génération de réponses avec citations des sources
- Historique des conversations
- Jeu de tests pour mesurer la pertinence des réponses

## STACK TECHNIQUE
Next.js  ·  FastAPI  ·  LangChain  ·  PostgreSQL  ·  pgvector  ·  Sentence Transformers  ·  LLM API  ·  Docker

### CONTRAINTE 
Budget strict de **0 €** pour le développement et la démonstration publique,
tous services compris. Projet personnel destiné au **CV**, sans objectif commercial.

## CADRAGE V1

La V1 inclut une authentification, une bibliothèque privée par utilisateur et
un hébergement public sur Vercel. **Groq Free** avec `openai/gpt-oss-120b` est
retenu pour la génération ; **multilingual-e5-small** pour les embeddings CPU.
L'authentification est **Better Auth avec `prenom.nom` / mot de passe**, dans Next.js,
avec sessions dans PostgreSQL local, puis Neon Free au jalon Vercel. Aucun e-mail ni compte externe requis. L'URL publique sera sur **`vercel.app`**.

- [Spécification et étapes V1](docs/specification.md)
- [Décision technique](docs/decisions/0001-groq-et-architecture-v1.md)
- [Budget zéro et authentification](docs/decisions/0002-budget-zero-et-authentification.md)
- [Étape 0 validée : preuves, budget et contrôles planifiés](docs/etape-0-faisabilite.md)
- [Corpus initial et reproduction des essais locaux](evaluation/README.md)

Le cadrage, les essais CPU et l'appel Groq réel sont réalisés. Le porteur a
confirmé le niveau **Free** du compte Groq. Le projet **assistant-rag** existe
sur Vercel Hobby ; une Preview en `fra1` exécute FastAPI, E5 embarqué et Groq.
La recherche de l'extrait fictif, la réponse et sa référence ont été vérifiées.
Voir le [prototype et ses commandes](probes/vercel/README.md) et les
[preuves Vercel](evaluation/reports/vercel-step0.json).

Cette Preview conserve la protection Vercel et un jeton serveur pour les essais.
**L'étape 0 est validée sur le périmètre approuvé par le porteur.** L'étape 1
met en place le socle local ; l'identité arrive à l'étape 2, le stockage privé
et la file à l'étape 3. Les qualifications cloud seront regroupées à un jalon
ultérieur. Le développement courant ne déclenche aucun déploiement Vercel.
Tous les composants doivent rester sur les offres gratuites : aucune souscription
payante, aucun domaine acheté et aucune facturation de dépassement. Si un quota
est atteint, l'opération est suspendue. La qualification et la publication V1 restent à terminer.

## LANCEMENT LOCAL

Depuis Ubuntu/WSL, avec Docker et Compose v2 disponibles :

```bash
cd /home/daniel/assistant-rag
python3 scripts/local/bootstrap.py
docker compose build backend frontend
docker compose build worker
python3 scripts/local/prepare_embeddings.py --download
docker compose up -d --wait
```

Ouvrir [l'application locale](http://localhost:3000) et cliquer sur
« Vérifier la connexion », ou ouvrir `/sign-up` pour créer un compte. L'API est sur `localhost:8000`, PostgreSQL/pgvector
sur `localhost:5433`. Compose applique les migrations avant de lancer l'API.

```bash
bash scripts/local/check.sh
```

Les contrôles incluent tests API, migrations et vecteurs sur une base isolée,
lint, types, build, navigateur bureau/mobile et persistance après recréation du
conteneur PostgreSQL. Aucun appel LLM ni service cloud n'est nécessaire.

La configuration locale `.env` est générée sans modifier `.env.local` ni sa clé
Groq. [Guide local, commandes et persistance](docs/developpement-local.md).
Le prototype de l'étape 0 et sa configuration Vercel sont conservés séparément.

**Étape 1 validée en local :** 13 tests réussis, lint/types/build et persistance
vérifiés. [Résultats et limites déclarées](docs/etape-1-socle-local.md).
**Étape 2 validée en local :** inscription, connexion et déconnexion par
`prenom.nom` / mot de passe ; sessions et isolation vérifiées. **38 tests** passent,
avec lint/types/build et persistance. Aucun déploiement Vercel.
[Créer un compte local](http://localhost:3000/sign-up) ·
[Rapport et limites](docs/etape-2-identite-locale.md) ·
[Choix d’authentification](docs/decisions/0003-identifiants-locaux.md).
**Étape 3 validée en local :** import privé PDF/DOCX/TXT, texte localisable,
déduplication par compte, relance, reprise et suppression. **59 tests** passent,
avec un envoi direct réel de 20 Mio sur bureau/mobile et la persistance de dix
documents de test après recréation des services. Aucun appel LLM ni déploiement.
[Ouvrir la bibliothèque](http://localhost:3000/library) ·
[Rapport et limites](docs/etape-3-import-local.md) ·
[Choix de l’import durable](docs/decisions/0004-import-local-durable.md).
**Étape 4 validée en local :** découpage exact avec repères physiques, embeddings E5 CPU hors ligne,
checkpoints, quotas de passages et publication atomique. Le document devient
« Prêt » quand tous ses vecteurs sont enregistrés ; ses passages sont consultables.
**77 tests** passent, avec lint/types/build et conservation des dix index de test
après remplacement des services. Aucun appel LLM ni déploiement Vercel.
[Rapport et paramètres](docs/etape-4-indexation-locale.md) ·
[Choix de l’indexation](docs/decisions/0005-indexation-locale-reprenable.md).
**Étape 5 validée en local :** recherche privée avec sélection documentaire,
texte source consultable et scores, E5 réel et distance cosinus exacte.
**100 tests** passent avec lint/types/build ; les dix-huit originaux, textes,
index et résultats de recherche restent identiques après remplacement des services.
Recall@5 de développement : **82,4 %**, seuil **0,84** ; dix cas finaux réservés.
Le seuil ne rejette qu’une des trois questions hors corpus : l’abstention de
l’assistant reste à qualifier à l’étape 6. Aucun appel LLM ni déploiement Vercel.
[Ouvrir la recherche](http://localhost:3000/search) ·
[Rapport et limites](docs/etape-5-recherche-locale.md) ·
[Choix de recherche](docs/decisions/0006-recherche-privee-et-seuil.md).
**Étape 6 validée techniquement en local :** réponses avec Groq Free, preuves
textuelles vérifiées et sources privées consultables, abstention et quotas
PostgreSQL partagés. L’envoi au fournisseur demande un accord dans l’interface.
**130 tests** passent ; 26 documents/index/recherches et les compteurs de
génération persistent après remplacement des services.
Trois réponses Groq instrumentées ont été évaluées sur des fixtures publiques :
deux réponses étayées et une abstention correcte, mais une réponse comparative
reste partielle. Les dix cas finaux restent réservés. Aucun déploiement Vercel.
[Essayer une réponse](http://localhost:3000/search) ·
[Rapport, appels réels et limites](docs/etape-6-reponses-locales.md) ·
[Décision de génération](docs/decisions/0007-generation-sources-et-quotas.md).
**Étape 7 validée en local :** conversations et historique privés.
Création, reprise, suivis et suppressions depuis l’interface ; questions, réponses,
sélections et citations conservées dans PostgreSQL. Les extraits sont retirés
lorsqu’une source est supprimée. **156 tests** passent, avec lint/types/build et
conservation de 16 conversations, 20 échanges et 10 sources après remplacement
des services. Aucun déploiement Vercel ni appel Groq réel supplémentaire.
[Mes conversations](http://localhost:3000/conversations) ·
[Parcours et preuves](docs/etape-7-conversations-locales.md) ·
[Choix de la persistance](docs/decisions/0008-conversations-privees-et-reprise.md).

**Étape 8 achevée : application publiée sur [Vercel](https://assistant-rag-three.vercel.app).**
Inscription par nom d’utilisateur/mot de passe, imports privés, E5 et appels
Groq réels fonctionnent dans le cloud. Le nouveau lot réservé atteint 100 %
de Recall@5, 8/8 réponses complètes et 2/2 abstentions ; la grille des citations
a été relue et validée par le porteur. Le premier lot en échec reste publié.
Le correctif final passe la non-régression : 7/8 réponses complètes (87,5 %),
15/15 références valides et 2/2 abstentions, sans erreur technique. Le parcours
bureau/mobile, l’isolation, la persistance après redéploiement, les sauvegardes
et les performances sont vérifiés. Les limites et conditions sont publiées.
[Rapport de publication](docs/etape-8-publication.md) ·
[Grille de qualité](docs/revue-qualite-etape-8.md) ·
[Exploitation, budget et sauvegardes](docs/deploiement-vercel.md).

La démonstration est bornée à 10 tentatives Groq/jour/compte, 50 globalement et
2/minute. Les tentatives refusées par le contrôle de citations consomment aussi
le quota ; une telle réponse est affichée comme une erreur et peut être renvoyée
ultérieurement. Aucun dépassement payant ni déploiement automatique à chaque push.

## Interface conversationnelle

Après connexion, le chat est l’écran principal. Le bouton **+** permet d’ajouter
un ou plusieurs PDF, DOCX ou TXT directement dans la bibliothèque privée.
L’interface suit leur préparation, conserve la question en cours et crée la
conversation au premier envoi. L’historique et la bibliothèque sont accessibles
dans une barre latérale, repliée en menu sur mobile. Les sources restent vérifiables
et l’accord d’envoi à Groq est demandé pour chaque réponse.

Cette évolution est publiée sur [Vercel](https://assistant-rag-three.vercel.app)
depuis le 14 octobre 2026. Connexion, import multiple, brouillon, historique,
sources, navigation mobile et déconnexion ont été vérifiés en production.
Voir le [journal de déploiement](docs/deploiement-vercel.md#refonte-conversationnelle--14-octobre-2026).

### Identité et interface inspirée des maquettes (publiée le 14 octobre 2026)

Nom public : **My Talking RAG**. Logo vectoriel original à deux rubans de citation
entrelacés, également utilisé pour le favicon. Les cartes sous
chaque réponse présentent le fichier, son repère et un extrait exact ; les liens
de citation ouvrent un panneau latéral avec les citations et le passage complet.
« Voir le document » ouvre son texte extrait dans la bibliothèque privée.

La bibliothèque propose une recherche par nom et les filtres PDF, DOCX et TXT.
Les paramètres permettent de choisir **Clair**, **Sombre** ou **Système**. Le choix
est mémorisé un an par un cookie d’apparence sans donnée privée ; aucun jeton
ou document n’est enregistré durablement dans le navigateur. Le système est suivi par CSS, y
compris lorsqu’il change, sans flash volontaire d’un autre thème au chargement.
Aucun sélecteur de modèle ni réglage de recherche n’est exposé. Cette évolution est publiée sur
<https://assistant-rag-three.vercel.app>.

Contrôles : lint, TypeScript et build réussis ; 59/60 tests navigateur réussis
au premier passage, le dernier bloqué par les 100 documents de test accumulés.
Après réinitialisation de la seule base de test, les 6 tests de recherche
bureau/mobile passent, couvrant le cas restant. Les 38 tests d’intégration passent
aussi. Les captures des thèmes, de la bibliothèque et des sources ont été relues.

La navigation utilise une barre d’icônes persistante. Le logo ouvre ou
masque le panneau latéral avec l’historique et le compte ; les raccourcis
Nouvelle discussion, Documents et Paramètres restent accessibles en mode compact.
Les libellés apparaissent au survol ou au focus. Le bandeau supérieur a été retiré.

L’accueil se limite à « Par où commence-t-on ? », la saisie avec le + et
les contrôles utiles (périmètre documentaire, état et consentement Groq).
Les titres et textes redondants ont été retirés des autres pages. Les paramètres
présentent le thème et un volet de confidentialité ; les limites de la bibliothèque
et l’état du service sur l’accueil public se consultent à la demande.

Vérification de cette simplification : lint, typage et build réussis. Le lot de
32 tests navigateur a révélé un panneau de sélection recouvrant l’envoi sur mobile
(31 réussites). Après correction de sa fermeture au changement de focus, les
8 tests ciblés bureau/mobile passent : import multiple, reprise après erreur,
conversation complète et import des trois formats. Les captures ont été relues.
Ces contrôles locaux n’ont effectué aucun appel Groq réel.

Publication de cette version : commit `c0d623d`, déploiement Vercel de production
`dpl_E2WLfpyHd3McxPUxwAbe1NyuRA7Z` (`READY`). Les huit contrôles publics passent :
identité/accueil, import multiple, thèmes persistants, filtre documentaire,
historique/sources, navigation mobile, déconnexion et isolation intercomptes.
La vérification réutilise les réponses de qualification existantes, sans nouvel
appel Groq. Voir le [journal de publication](docs/deploiement-vercel.md#my-talking-rag--14-octobre-2026).
