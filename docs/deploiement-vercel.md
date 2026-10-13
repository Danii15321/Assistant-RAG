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
