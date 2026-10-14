# ADR 0011 — OpenAI et plafond d’essai global de 1 dollar

- Date : 14 octobre 2026.
- Décision autorisée par le porteur : ajouter OpenAI en local, garder Groq par
  défaut et limiter les premiers essais à 1 USD sur ses 19 USD de crédits existants.
- Extension explicitement autorisée : publication OpenAI sur Vercel avec transfert
  du budget restant et désactivation locale. Exception ciblée aux ADR 0002 et 0007.

## Fonctionnement

Choix explicite par question : Groq (`openai/gpt-oss-120b`), GPT-6 Luna
(`gpt-6-luna`) ou GPT-6.1 Sol (`gpt-6.1-sol`). Nouvelle discussion : Groq.
Aucun fallback vers un modèle payant, aucune relance automatique OpenAI.
Le consentement nomme le fournisseur et est réinitialisé lors du changement.
Le modèle demandé est enregistré avec l’échange, intégré à l’idempotence et
restitué dans la réponse. Les requêtes Groq enregistrées auparavant restent rejouables.

L’extraction, E5, la recherche privée, les sources et leur validation restent
communs. Sans passage pertinent, aucune génération externe. L’adaptateur utilise
Chat Completions, une réponse JSON structurée, `store: false`, le niveau de service
`default`, sans outil ni téléchargement de fichier chez OpenAI. Le stockage désactivé
ne remplace pas les règles de rétention du fournisseur ; seuls la question, les
questions historiques utiles et les extraits sélectionnés sont envoyés.

L’accès effectif à chaque modèle dépend du projet OpenAI. La présence d’une clé
rend l’option sélectionnable ; une erreur d’accès produit une erreur explicite,
sans changement automatique de fournisseur.

## Plafond conservateur

Le plafond **global et cumulatif de 1 000 000 micro-USD (1 USD)** est stocké dans
PostgreSQL, commun aux comptes et aux deux modèles. Avant chaque tentative HTTP,
une transaction réserve **0,01 USD pour Luna** ou **0,12 USD pour Sol**. Une mise à
jour conditionnelle atomique refuse les réservations qui dépasseraient le plafond.
Les erreurs, expirations, sorties rejetées et interruptions gardent leur réserve ;
elle n’est jamais restituée automatiquement. Le compteur représente donc une
**borne prudente, pas la facture OpenAI**. L’usage réel en tokens est enregistré
dans les tentatives de génération existantes quand une réponse exploitable arrive.

Au maximum : 100 tentatives Luna, ou 8 Sol et 4 Luna, avant arrêt. Les quotas
existants (2 tentatives/minute globalement, 10/jour/compte, 50/jour globalement,
155 000 tokens réservés/jour) peuvent arrêter plus tôt. Une tentative OpenAI
réserve 24 576 tokens dans ce compteur journalier ; Groq garde 3 100.

Base du calcul : corps JSON UTF-8 limité à 16 000 octets, comprenant messages et
schéma, plus marge de 4 096 tokens pour l’encadrement. Une borne d’un token par
octet est conservatrice pour le texte ; le découpage du contexte reste limité par
le budget existant. Sortie maximale, raisonnement inclus : 1 200 tokens Luna,
4 096 Sol. Effort `none` sur Luna, `low` sur Sol. Aucun mode rapide ni traitement
régional explicitement demandé.

Tarifs officiels vérifiés le 14 octobre 2026, pour un million de tokens :

| Modèle | Entrée standard | Écriture cache (borne retenue) | Sortie |
|---|---:|---:|---:|
| GPT-6 Luna | 0,10 USD | 0,125 USD | 0,50 USD |
| GPT-6.1 Sol | 2,00 USD | 2,50 USD | 10,00 USD |

Borne Luna : 20 096 × 0,125 / 1M + 1 200 × 0,50 / 1M = 0,003112 USD.
Borne Sol : 20 096 × 2,50 / 1M + 4 096 × 10 / 1M = 0,0912 USD.
Les réserves arrondies couvrent aussi une marge supérieure à 10 %. Aucun avantage
de cache n’est présumé. Les appels sont bloqués après le 14 novembre 2026 jusqu’à
revue des tarifs et des limites ; les alias de modèles exigent cette vigilance.

Sources : [Luna](https://developers.openai.com/api/docs/models/gpt-6-luna),
[Sol](https://developers.openai.com/api/docs/models/gpt-6.1-sol),
[tarification](https://developers.openai.com/api/docs/pricing),
[rétention](https://developers.openai.com/api/docs/guides/your-data).

Le plafond protège les appels de **cette application et son compteur actif de production**.
Il ne mesure pas les dépenses d’autres programmes utilisant la même clé ou le
même projet OpenAI. Ne pas réinitialiser la base ni restaurer un ancien compteur
pour poursuivre les essais ; cela effacerait la mémoire des montants engagés.
Aucune recharge, activation de paiement ni changement de plafond n’est effectué.

## Secrets et déploiement

La clé initiale reste dans `.secrets/openai_api_key`, hors Git, mode 600.
Elle est transmise par stdin à Vercel et conservée comme secret serveur
`OPENAI_API_KEY` de Production uniquement. Aucun préfixe `NEXT_PUBLIC_`.
L’adaptateur ne lit le secret d’environnement qu’en cloud ; en local il lit le
fichier. L’activation cloud demande `OPENAI_CLOUD_ENABLED=true`, `CLOUD_RUNTIME=true`
et `VERCEL_ENV=production`. Une Preview reste bloquée même avec le drapeau activé.
Les secrets du projet Vercel sont accessibles aux services serveur ; seul le
backend lit cette clé. Aucun code frontend, worker ni test ordinaire ne l’utilise.

`OPENAI_LOCAL_ENABLED=false` dans Compose. Avant transfert, arrêter le backend
local, exporter le journal privé des réservations et verrouiller son compteur à
1 000 000 micro-USD dans une transaction. Ainsi, réactiver accidentellement le
drapeau ne débloque pas une seconde enveloppe. Le journal réel reste intact.
Importer ensuite les tentatives locales avec leurs UUID dans la base de production,
sous verrou du compteur, en ajoutant seulement les montants non encore présents.
L’import est idempotent ; aucune réserve n’est remboursée. Le transfert du
14 octobre comprend 10 000 micro-USD engagés, donc 990 000 disponibles avant
les contrôles de publication. L’enveloppe totale reste 1 USD pour tous les comptes.
Le fichier opérateur et la preuve privée sont dans `evaluation/.qa/` (hors Git).
Ne pas restaurer une ancienne base locale pour contourner ce verrou.

## Migration et retour arrière

`0009_openai_trial` ajoute le modèle à `conversation_exchanges` (défaut Groq) et
les tables `openai_trial_budget` / `openai_trial_attempts`. Sauvegarder base et
originaux privés avant application. Les tests utilisent exclusivement
`assistant_rag_test`. La migration n’altère pas les textes, vecteurs ou sessions.

Le downgrade retire uniquement la colonne de sélection ; **les deux tables de
budget sont conservées**, et un upgrade les réutilise sans remise à zéro. Pour
revenir au code précédent, arrêter l’API, revenir à `0008_cloud_wakeups`, puis
relancer ce code. Les réponses JSON existantes conservent leur champ `model`.
Ne jamais restaurer un dump antérieur aux appels payants sans réconcilier au
préalable les montants réservés. Une copie des journaux de budget postérieurs aux
appels doit être conservée avec les sauvegardes.


## Vérification locale du 14 octobre 2026

- 98 tests unitaires, 41 tests d’intégration PostgreSQL réussis ; incluent réserve
  concurrente, plafond exact, conservation après rollback, idempotence et sources.
- 36 parcours Playwright sur bureau/mobile : 34 parcours existants réussis, puis
  les 2 nouveaux après correction du test d’option désactivée. Le matcher
  `toBeDisabled` ne classait pas les `<option>` ; vérification de leur propriété
  native `disabled` à la place, sans assouplir le contrôle produit.
- Ruff, format, mypy, ESLint, TypeScript et build Next.js réussis.
- Interface locale inspectée dans le navigateur : Groq sélectionné, modèles
  OpenAI désactivés tant que la clé manque ; rendu sombre harmonisé.
- Sauvegarde avant migration : `evaluation/.qa/backups/openai-local-20261014T120736Z/`,
  dump PostgreSQL et originaux privés, hors Git. Migration locale appliquée ;
  backend, frontend, base et worker relancés. Budget réservé lu en base : 0.
- Clé absente à cette vérification : **aucun appel OpenAI réel effectué**,
  compatibilité d’accès du compte et qualité des réponses réelles encore à vérifier.
  Les suites ordinaires emploient un transport OpenAI simulé et Groq simulé.
- Aucun déploiement, changement cloud, commit ou push.


## Correctif du premier essai réel — 14 octobre 2026

Le premier essai utilisateur a échoué avant l’appel OpenAI : la contrainte SQL
historique de `generation_attempts.reserved_tokens` limitait chaque réservation
à 3 100 tokens, alors que le chemin OpenAI réserve 24 576. Le compteur monétaire
était encore à zéro. Les tests précédents des deux compteurs séparés n’avaient pas
couvert leur utilisation conjointe dans `AnswerService`.

La migration `0010_generation_token_capacity` relève cette borne par tentative
à 24 576, sans modifier le plafond journalier de 155 000 ni le plafond de 1 USD.
Les tests d’intégration reproduisent désormais une réponse citée via l’adaptateur
OpenAI simulé, le service réel et les deux repositories PostgreSQL. Ils échouaient
sur la contrainte avant correction, puis passent pour Luna et Sol.

Le downgrade de 0010 réinstalle la borne 3 100 avec `NOT VALID` : elle s’applique
aux nouvelles écritures et conserve les anciennes réservations OpenAI dans les
compteurs. Aucun compteur de tokens ou d’argent n’est remis à zéro. Un upgrade
ultérieur valide à nouveau la borne 24 576. Sauvegarde locale privée préalable :
`evaluation/.qa/backups/openai-token-fix-20261014T123117Z/`.

Le sélecteur reprend aussi le modèle du dernier échange lors de la réouverture
d’une conversation, y compris après un échec. Une nouvelle discussion conserve
Groq par défaut ; le consentement doit toujours être renouvelé.


Validation après correctif : 98 tests unitaires, 44 tests PostgreSQL, 6 parcours
navigateur ciblés bureau/mobile, Ruff/format/mypy/ESLint/TypeScript/build réussis.
La clé est reconnue et l’API des modèles confirme l’accès aux deux modèles choisis.
Un appel **réel GPT-6 Luna** sur texte fictif Oriole a produit une réponse et des
citations validées : 392 tokens d’entrée, 47 de sortie, 2,93 secondes.
[Preuve sans secret ni document privé](../../evaluation/reports/openai-local-smoke.json).
Réservation prudente de 0,01 USD, reste 0,99 USD ; ce compteur n’est pas une facture.
Le navigateur a refusé l’accès à la discussion utilisateur pour le contrôle réel :
elle n’a pas été rejouée et aucun document privé n’a été transmis lors de cet essai.
L’ancien échange échoué est conservé ; actualiser puis envoyer une nouvelle question.
Aucun déploiement Vercel, commit ou push.


## Publication autorisée et vérifiée — 14 octobre 2026

Le porteur a ensuite autorisé explicitement OpenAI en production avec transfert
du budget restant. Le journal de publication décrit la migration, le verrou local,
les contrôles et le rollback. Deux réponses réelles, une par modèle, ont été
vérifiées sur le corpus fictif Iris, avec citations et idempotence. Réserve totale
après publication : 0,14 USD, solde prudent 0,86 USD. Les preuves locales ci-dessus
restent historiques ; les règles actuelles de secrets et activation sont celles
de la section « Secrets et déploiement ».
[Rapport](../../evaluation/reports/openai-release-2026-10-14.json).
