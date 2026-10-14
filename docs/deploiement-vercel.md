# Déploiement Vercel — Assistant RAG

L’application utilise le projet `assistant-rag` de `danii15321s-projects`.
URL de production publique : <https://assistant-rag-three.vercel.app>.
Consulter le rapport de l’étape 8 avant de considérer une qualification acquise.

## Ressources et budget

Vercel Hobby confirmé par l’API du compte ; Neon provisionné explicitement avec
`--plan free_v3`, en `fra1`, sans Neon Auth ; Better Auth existant est conservé.
Les stores Blob sont privés. Aucun essai Pro, carte, domaine ou service payant.

| Ressource | Production | Preview |
| --- | --- | --- |
| Neon | `assistant-rag-production` | `assistant-rag-preview` |
| Blob | `store_ZNzVxmZQHYjR7BIR` | `store_urItJkBv2m1fID5Y` |
| Quota applicatif de stockage global | 400 Mio | 100 Mio |
| Groq | Free confirmé par le porteur | Désactivé |

Inclusions publiées au 12 octobre 2026 : Blob 1 Go, 10 Go de transfert,
2 000 opérations avancées et 10 000 simples ; Queues un million d’opérations ;
compute 4 heures CPU actives, 360 Go-heures mémoire, un million d’invocations.
Les quotas Vercel sont partagés avec les autres projets de l’espace. Neon Free
annonce 100 CU-heures. Le plan Marketplace `free_v3` réellement provisionné
indique **0,5 Go de base par projet**, même si la page commerciale générale
présente d'autres inclusions : retenir la limite du compte. L'indexation s'arrête
à 400 Mio de base occupée pour garder une marge ; les uploads Preview s'arrêtent
dès 100 Mio. Le transfert réseau gratuit annoncé est de 5 Go.
À limite atteinte, attendre le renouvellement ou réduire l’usage ; ne pas changer
de plan. Vérifier de nouveau les offres avant tout nouveau provisionnement.

## Variables serveur

La connexion CLI et `.vercel/project.json` restent locales et ignorées par Git.
Les secrets se renseignent par stdin, jamais avec `--value` dans un historique.

| Variable | Usage |
| --- | --- |
| `CLOUD_RUNTIME=true` | Active Blob et les consommateurs bornés |
| `AUTH_DATABASE_URL` | Connexion poolée Neon pour Better Auth et le throttle |
| `DATABASE_URL_UNPOOLED` | Connexion directe Neon TLS pour FastAPI/verrous |
| `BETTER_AUTH_SECRET` | Secret aléatoire distinct par environnement |
| `APP_PUBLIC_URL` | URL stable en Production ; absent en Preview, qui utilise `VERCEL_URL` |
| `INTERNAL_WORKER_SECRET` | Secret aléatoire pour les communications internes |
| `CRON_SECRET` | Secret du cron Vercel |
| `BLOB_READ_WRITE_TOKEN` | Secret du store privé lié à cet environnement |
| `BLOB_HOST` | Hôte exact du store privé, sans protocole ni chemin |
| `GLOBAL_STORAGE_BYTES` | 419430400 en Production, 104857600 en Preview |
| `GROQ_API_KEY` | Secret uniquement en Production |
| `LLM_FREE_PLAN_CONFIRMED` | `true` uniquement après vérification du compte Free |

`API_INTERNAL_URL` est injectée par le binding Vercel de l’interface vers le
serveur. Les bindings circulaires sont interdits : le serveur joint les routes
de l’interface via `APP_PUBLIC_URL` ou l’URL de sa propre Preview (`VERCEL_URL`),
avec son jeton OIDC Vercel et le secret interne pour Blob. Aucun de ces secrets
n’est transmis lors du téléchargement direct d’un original Blob.
Aucune variable privée ne porte le préfixe `NEXT_PUBLIC_`.

## Procédure de publication

1. Exécuter les contrôles locaux : `bash scripts/local/check.sh`.
2. Vérifier projet, espace, plan et environnement avec la CLI épinglée :
   `npx --yes vercel@63.1.2 project inspect --non-interactive`.
3. Exporter la base et les originaux dans un répertoire local privé ignoré.
   Ne jamais importer la base de production dans une Preview.
4. Appliquer les migrations Alembic sur une connexion **directe** de la cible,
   après sauvegarde. Ne pas lancer les tests de remise à zéro sur Neon.
5. Déployer une Preview avec `npx --yes vercel@63.1.2 deploy --target preview --yes`.
   Tester l’inscription, les imports privés, E5 et l’isolation. La génération y
   est volontairement désactivée ; les erreurs Groq sont couvertes localement.
6. Déployer la Production avec `npx --yes vercel@63.1.2 deploy --prod --yes`, puis
   vérifier l’URL stable sans connexion Vercel, avec deux comptes applicatifs.
7. Exécuter le parcours complet et les contrôles de persistance après un second
   déploiement du même code. Publier les preuves et les écarts, sans secrets.

Les commandes s’exécutent à la racine du dépôt lié. Vérifier la cible avant chaque
mutation. Les migrations sont séparées du build : aucun déploiement ne doit
modifier implicitement le schéma d’une base inconnue.

## Reprise, suppression et rollback

Les jobs sont stockés dans PostgreSQL. Un crash libère le verrou CPU ; après
expiration du bail, une livraison Queues reprend le lot. Le client peut relancer
un document en échec. Le cron `/api/internal/reconcile`, protégé par `CRON_SECRET`,
s’exécute quotidiennement à 04:17 UTC. Sans visite, un réveil perdu peut attendre
ce cron. Les suppressions excluent immédiatement les passages et nettoient les
octets lors du traitement du job de suppression.

Un rollback Vercel restaure le code, pas la base ni les fichiers. La migration
`0008_cloud_wakeups` est additive. Revenir au code local antérieur ne constitue
pas un rollback cloud fonctionnel : utiliser un déploiement cloud qualifié.
Avant un rollback, vérifier sa compatibilité avec le schéma courant, puis utiliser
`vercel rollback <déploiement-qualifié>`. Une restauration de données exige un
arrêt des écritures, la sauvegarde actuelle et une cible explicitement vérifiée.

Les exports locaux gratuits doivent inclure les originaux Blob et un `pg_dump`
au format custom, ainsi qu’un manifeste SHA-256. Les conserver hors Git, droits
0700 pour le répertoire et 0600 pour les fichiers. Ne pas activer de snapshot
planifié payant. Tester la restauration sur une base locale isolée.

L’outil `node scripts/cloud/backup.mjs production` exporte la base Neon et les
originaux dans `evaluation/.qa/backups/` (ignoré par Git), puis restaure le dump
dans un conteneur PostgreSQL 18/pgvector temporaire, sans port exposé. Il compare
les nombres de lignes et les empreintes du contenu, vecteurs compris, puis
supprime uniquement ce conteneur de restauration. Le résultat public ne contient
aucun original, mot de passe, cookie ou URL signée. Exécuter sans écritures
concurrentes ; une différence pendant l’export invalide l’essai.

L’outil lit `evaluation/.qa/production.env`, obtenu par `vercel env pull` pour
l’environnement explicitement choisi, et utilise les dépendances installées dans
`frontend/`. Docker et le bundle de certificats système Ubuntu sont nécessaires.
Il ne restaure jamais de données dans Neon. La restauration des octets Blob reste
une opération de récupération à préparer séparément ; l’export les conserve avec
leurs UUID et leurs empreintes SHA-256.

## Mesures et qualification bornée

Les résultats sont consignés dans `evaluation/reports/` et résumés dans
[le rapport de publication](etape-8-publication.md). Les scripts cloud utilisent
uniquement des comptes synthétiques et le corpus CC0. Un marqueur privé réserve
chaque appel réel avant envoi ; réconcilier un appel interrompu avec l’historique
et le compteur partagé avant toute reprise. Ne pas supprimer un marqueur pour
relancer aveuglément, ni réinitialiser les quotas.

`python3 scripts/cloud/summarize_performance.py` consolide les mesures déjà
enregistrées, sans appel réseau. Les versions de prompt, erreurs et démarrages
à froid sont conservés ; ce cumul ne vaut pas trente appels sur le seul prompt
final. `python3 scripts/cloud/metrics.py --url https://assistant-rag-three.vercel.app --environment production --embedding` sollicite une sonde interne authentifiée :
phrase fixe, premier puis second encodage, RSS ponctuelle du processus et de son
encodeur. La clé provient du fichier privé de qualification ; aucune donnée
documentaire n’est renvoyée. Ne pas activer Observability Plus pour cette mesure.

Les déploiements restent manuels : le dépôt GitHub n’est pas connecté à un
déploiement automatique à chaque push. Regrouper les changements et vérifier
les contrôles avant un prochain jalon de publication.

## Refonte conversationnelle — 14 octobre 2026

Publication demandée par le porteur après les contrôles locaux (lint, types,
build et parcours navigateur bureau/mobile). Déploiement de production
`dpl_2kCgdcbia7VVGsAEBXM8Bq47DEUK`, statut `READY`, construction et publication
en environ quatre minutes ; URL stable : <https://assistant-rag-three.vercel.app>.
Projet et espace vérifiés, plan Hobby confirmé. Aucun changement de schéma,
de secrets ou de ressources cloud. Aucun commit ni push effectué à ce jalon :
source issue de `8d4a3aa` avec la refonte locale, empreinte SHA-256 des 24 fichiers
modifiés avant publication :
`81dd8572addf6fed4d56fc351e16f30f142744798e8b8443588b2aa062dec68c`.

Contrôles Playwright sur l’URL publique, avec un compte synthétique existant :
connexion vers le chat, sélection multiple via « + », deux uploads dédupliqués
(TXT et DOCX), brouillon conservé, consentement obligatoire, historique et
sources persistants, absence de débordement mobile, menu au clavier et
déconnexion avec API protégée. Tous réussis. Aucun nouvel appel Groq pour
ce contrôle ; les réponses consultées proviennent de la qualification antérieure.
Aucune erreur retournée par les journaux Vercel du nouveau déploiement sur
la fenêtre de quinze minutes contrôlée après publication.

## My Talking RAG — 14 octobre 2026

Version validée par le porteur puis publiée depuis le commit
`c0d623d46a5f49ffb222d063e9e4394a793aad4a`, poussé sur `origin/main`.
Déploiement `dpl_E2WLfpyHd3McxPUxwAbe1NyuRA7Z`, cible Production,
statut `READY`, construction/publication en environ six minutes.
URL stable : <https://assistant-rag-three.vercel.app>.
URL immuable : <https://assistant-cj0bmnjlw-danii15321s-projects.vercel.app>.
Projet `assistant-rag`, espace `danii15321s-projects`, plan Hobby vérifiés avant
publication. Aucun changement de schéma, secret, plan ou ressource cloud.

La version regroupe la nouvelle identité/logo, les thèmes Clair/Sombre/Système,
les cartes et le panneau de sources, la navigation compacte et les pages épurées.
Lint, typage, build et contrôles locaux documentés dans le README ; le build
Vercel a aussi compilé et typé le frontend avec succès.

Les huit vérifications Playwright publiques passent avec deux comptes
synthétiques existants : accueil, sélection/import de deux fichiers déjà présents
et brouillon conservé, consentement obligatoire, trois thèmes avec persistance,
filtre documentaire, historique et sources existantes après rechargement,
navigation mobile/clavier, déconnexion et refus intercompte (`404`). Les captures
bureau/mobile ont été relues. Aucun nouvel appel LLM : les réponses consultées
proviennent de la qualification Groq antérieure. Les documents `corrompu.pdf` et
`scan.pdf` restent volontairement en échec (`invalid_file`, `no_text`).

La lecture des journaux du déploiement sur quinze minutes retourne deux
avertissements `pg-connection-string` classés « error » par Vercel ; les requêtes
associées ont réussi (`200`). Ils annoncent une évolution future de la sémantique
SSL, sans échec constaté lors de cette vérification. Les connexions actuelles
restent vérifiées ; requalifier les options TLS lors d’une mise à jour de `pg`.
Aucun service de suivi payant ajouté.

[Preuve synthétique sans secrets](../evaluation/reports/interface-release-2026-10-14.json).
Rollback du code possible vers `dpl_2kCgdcbia7VVGsAEBXM8Bq47DEUK` ; aucune migration
n’accompagne cette publication. La documentation de publication est commitée
séparément du code exécuté. Les déploiements restent manuels.


## OpenAI et correction de réservation — 14 octobre 2026

Publication autorisée avec transfert du budget restant vers Vercel et désactivation
locale. Production `dpl_Bz4YsavyH5JhVBeU2KvqFezmfXEb`, état `READY`, URL publique
<https://assistant-rag-three.vercel.app>, version immuable
<https://assistant-hj24qm8di-danii15321s-projects.vercel.app>.
Source : arbre de travail incluant l’évolution OpenAI non commitée, base Git
`0ac5d530f019`. Aucun commit, push ou branche créé par cette publication.

- Groq reste le défaut ; GPT-6 Luna et GPT-6.1 Sol exigent un choix explicite et
  le consentement avant chaque envoi. Aucun fallback payant.
- `OPENAI_API_KEY` est un secret de Production, transmis à la CLI par stdin ;
  `OPENAI_CLOUD_ENABLED=true`. Le code exige aussi `VERCEL_ENV=production`.
  Aucune clé ajoutée en Preview ni dans le bundle navigateur.
- OpenAI local désactivé dans Compose et compteur local verrouillé à 1 USD.
  L’unique tentative locale de 0,01 USD a été importée avec son UUID en production.
  Une répétition de cet import n’a ajouté aucune réservation.
- Deux appels réels publics sur le corpus fictif Iris : Luna et Sol répondent
  avec les ports attendus et une source valide. Chacun peut être rejoué avec le
  même identifiant sans nouvel appel ni nouvelle réservation.
- Réservations cumulées après validation : **0,14 USD**, reste **0,86 USD**.
  Ce sont des marges prudentes, pas une mesure de la facture du fournisseur.
  Les usages d’autres applications avec cette clé ne sont pas couverts.

Sauvegarde privée avant migration et restauration isolée réussies : 215 lignes
contrôlées et 27 originaux. Migrations 0009/0010 appliquées séparément du build,
puis comparaison des documents, unités, vecteurs, conversations, échanges et
citations : contenu inchangé (la nouvelle colonne `model` est exclue du digest
comparatif). Le budget n’a pas été remis à zéro. Contrôle de santé de la version
protégée via `vercel curl`, puis promotion vers l’URL publique.

Validation : 99 tests unitaires, 44 tests PostgreSQL, Ruff/format/mypy,
ESLint/TypeScript et build Next.js réussis. Neuf contrôles navigateur publics
passent : accueil, défaut Groq/sélecteur OpenAI, imports multiples et consentement,
thèmes, filtre bibliothèque, historique/sources/clavier, mobile, déconnexion,
isolation entre comptes. Le premier contrôle de déconnexion attendait strictement
`/sign-in`, alors que la révocation peut conduire à `/sign-in?expired=1` ; le test
accepte ces deux routes prévues et vérifie toujours le refus API 401 après sortie.
Les réponses privées d’utilisateurs n’ont pas été utilisées pour les essais.
Aucune réponse HTTP 5xx trouvée dans les logs de ce déploiement lors du contrôle.

[Preuve de publication](../evaluation/reports/openai-release-2026-10-14.json).
Les sauvegardes vérifient désormais aussi les deux tables de budget lorsqu’elles
existent. Conserver le journal le plus récent lors de toute restauration.

Retour arrière privilégié : désactiver `OPENAI_CLOUD_ENABLED` et redéployer cette
version, en conservant le schéma et le compteur. Un rollback vers la version
antérieure `dpl_E2WLfpyHd3McxPUxwAbe1NyuRA7Z` nécessite aussi le downgrade vers
`0008_cloud_wakeups` pour son contrôle de santé ; les tables de budget sont
conservées par les migrations. Sauvegarder avant toute opération et ne jamais
restaurer un compteur antérieur aux appels. Ne pas réactiver OpenAI local après
rollback : le transfert de l’enveloppe reste effectif.
