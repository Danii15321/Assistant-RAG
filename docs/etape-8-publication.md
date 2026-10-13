# Étape 8 — Qualification et publication

Qualification du 13 octobre 2026. **Étape 8 achevée : application publique,
appels Groq réels et critères V1 vérifiés, avec les limites ci-dessous.**

## Application et infrastructure

L’application publique est disponible sur <https://assistant-rag-three.vercel.app>.
Le dépôt [Assistant-RAG](https://github.com/Danii15321/Assistant-RAG) conserve
les étapes 0 à 8, les correctifs et les preuves de qualification.

Next.js et FastAPI/E5 s’exécutent sur Vercel ; Neon conserve les données,
Blob privé les originaux et Queues déclenche les travaux bornés. Preview et
Production ont des bases, stores et secrets distincts. Groq est désactivé en
Preview. Aucun service applicatif local ne fonctionnait pendant le lot final.

## Qualité et méthode

Le premier lot final est conservé : **62,5 % de Recall@5, 50 % de réponses
complètes, une erreur de citations**. Après la demande du porteur d’améliorer
la qualité, le seuil a été recalibré exclusivement sur le développement à 0,81.
Les extraits exacts sont attribués par le serveur ; les phrases voisines d’un
paragraphe restent ensemble dans la limite de 400 caractères. Voir ADR 0010.

Quatre nouveaux documents fictifs CC0 et dix questions ont été réservés avant
le gel de la version `grounded-claims-v5`. Les fichiers, paramètres et commit
sont consignés dans [le gel](../evaluation/reports/step8-freeze-v2.json).
Le lot n’a pas servi au réglage. Chaque question a été appelée une fois sur
Vercel, avec Groq réel et les compteurs de quota ordinaires.

| Indicateur | Nouveau lot | Objectif |
| --- | --- | --- |
| Recall@5, moyenne par question | 100 % sur 8 questions ; 10/10 passages | ≥ 80 % |
| Exactitude / complétude | 8/8, 100 % | ≥ 80 % |
| Références valides | 15/15, 100 % | 100 % |
| Affirmations fidèles | 13/13, 100 % | ≥ 90 % |
| Affirmations couvertes | 13/13, 100 % | ≥ 90 % |
| Abstention hors corpus | 2/2, 100 % | ≥ 80 % |
| Erreurs techniques du lot | 0/10 | Rapportées séparément |

Le porteur a relu et validé [la grille complète](revue-qualite-etape-8.md).
Cette revue humaine confirme l’analyse de l’agent ; elle n’est pas un audit
externe indépendant. H04 ajoute une comparaison correcte mais non demandée.
Les citations PDF peuvent couvrir une petite page entière. Ce petit corpus
synthétique ne garantit pas la qualité sur des documents longs ou spécialisés.

[Résultats initiaux](../evaluation/reports/quality-step8.json) ·
[Nouveau rapport](../evaluation/reports/quality-step8-v2.json) ·
[Réponses et sources réelles](../evaluation/reports/answers-step8-final-v2.json).

## Vérifications techniques acquises

- Preview : **38/38** contrôles ; Production : **38/38**. Inscription, trois
  formats, indexation E5, refus intercomptes, selection privée, fichiers invalides,
  20 Mio envoyés directement à Blob, déconnexion et accès internes protégés.
- Cycle de vie : **7/7**, dont expiration réelle d’une session synthétique,
  révocation, original privé inaccessible et suppression des passages par la file.
- Local : **80 tests unitaires**, **38 tests PostgreSQL**, lint et types Python
  et TypeScript réussis. Les **52 cas navigateur** sont couverts par la suite et
  les reprises ciblées détaillées dans le rapport local. Aucun test désactivé.
- Build de production v7 réussi. Aucune migration implicite dans le build.
- Export et restauration isolée PostgreSQL 18 réussis avec **122 lignes et
  22 originaux**, dont une conversation avec réponse, sources et erreurs
  persistées. Les empreintes des tables restaurées correspondent, vecteurs inclus.
  Les octets Blob sont exportés et hachés ; leur réimport dans un store de
  remplacement n’est pas effectué par cet exercice.

[Preview](../evaluation/reports/cloud-step8-preview.json) ·
[Production](../evaluation/reports/cloud-step8-production.json) ·
[Cycle de vie](../evaluation/reports/lifecycle-step8.json) ·
[Local](../evaluation/reports/local-checks-step8.json) ·
[Sauvegarde](../evaluation/reports/backup-step8-production.json).

## Incidents et limites à conserver

Le parcours navigateur a rencontré cinq rejets pour citations invalides sur le
corpus Iris avant correction. Aucune
réponse rejetée n’est publiée comme sourcée ; la question et l’état d’échec
restent dans l’historique. Le suivi navigateur réussit après le correctif v7 : 40 tokens, citation exacte et historique rechargé. Un défaut du
script de reprise a aussi renvoyé une question avant la fin du chargement de
l’historique ; le script attend maintenant le formulaire et vérifie le nouvel
échange. Les tentatives et leurs quotas sont conservés.

Les problèmes de publication antérieurs ont été corrigés : fichier de préparation
du modèle absent de l’archive, bindings circulaires, URL internes et rotation OIDC.
Les jetons internes ne sont jamais envoyés lors du téléchargement d’un original.

L’audit des dépendances installées signale zéro avis sur le runtime JavaScript,
mais cinq avis élevés dans l’outillage de développement via `braces`/ESLint,
sans correction compatible disponible lors de l’audit. Aucun motif utilisateur
n’alimente cet outillage. Le rapport ne prétend pas couvrir toutes les dépendances
Python par une analyse de vulnérabilités complète.

## Budget et exploitation

Vercel **Hobby actif sans essai** et Neon **Free `free_v3` sans carte requise**
sont confirmés par l’API du compte. Le plan Neon Marketplace indique **0,5 Go**
par projet ; le plafond d’indexation a été ramené à 400 Mio. Le niveau Groq Free
est confirmé par le porteur. URL `vercel.app`, aucun add-on ni domaine acheté.

Les limites partagées restent 10 tentatives Groq/jour/compte, 50 globalement,
2/minute et 155 000 tokens réservés/jour. Les échecs et retries comptent aussi.
Les offres et compteurs ne sont jamais augmentés ou remis à zéro pour qualifier.
La démonstration peut devenir indisponible au quota, jusqu’à son renouvellement.
Services, Container et Queues sont encore bêta ; un réveil perdu peut attendre
le cron quotidien sans visite. Aucun engagement de disponibilité continue.

[Budget vérifié](../evaluation/reports/budget-step8.json) ·
[Guide d’exploitation et rollback](deploiement-vercel.md).

## Reproduction et confidentialité

Les scripts `scripts/cloud/` utilisent seulement les fixtures CC0 et des comptes
synthétiques. Cookies, clés, dumps et journaux bruts restent dans `evaluation/.qa/`,
ignoré par Git. Les appels réels sont réservés avant envoi ; un appel interrompu
est réconcilié avant toute reprise. Aucun secret n’est publié dans les rapports.
Le guide décrit les migrations, sauvegardes et rollback : restaurer le code
ne restaure pas les données.

## Parcours et persistance

Le navigateur de production passe **10 contrôles** sur la version v7 :
connexion, uploads directs/dédoublonnés dans les trois formats et à 20 Mio,
deux réponses Groq réelles dans la même conversation (première en v5, suivi
en v7), source ouverte, historique rechargé, mobile sans débordement, absence
de session dans localStorage, déconnexion et refus 404 pour l’autre compte.
Les cinq échecs antérieurs restent explicitement conservés. Les captures
bureau/mobile ont été relues.

Les empreintes des documents, textes, vecteurs, conversations, échanges et
sources sont identiques avant et après un redéploiement réel. Le parcours v7
relit également la conversation créée sur une version antérieure.

[Parcours navigateur](../evaluation/reports/browser-step8.json) ·
[Persistance](../evaluation/reports/persistence-step8.json) ·
[Correctif reproduit sur la sortie capturée](../evaluation/reports/citation-boundary-step8.json).

## Mémoire et premier encodage

La sonde interne authentifiée mesure **970,11 Mio de RSS** pour le processus
et son encodeur E5 chargé, avec 2 048 Mio alloués. Ce relevé ponctuel n’est pas
un pic continu. Modèle initialement déchargé : premier encodage **9,789 s**,
second **31,33 ms** ; requête HTTP complète **15,122 s**. Le snapshot E5 pèse
environ 449 Mo. La sonde utilise uniquement une phrase synthétique fixe.
L’observabilité Vercel Plus n’a pas été activée car elle est payante.

[Mesure cloud](../evaluation/reports/embedding-cloud-step8.json) ·
[Portée de la mesure mémoire](../evaluation/reports/memory-step8.json).

## Non-régression du correctif final

Le déploiement final utilise le code `12fad41698b099f3daf98dabcccd120a7ed57174`
et le prompt `grounded-claims-v7|sentence-overlap-excerpts|harmony-budget2500|completion600`.
Après le correctif issu exclusivement du corpus de développement Iris, les dix
cas v2 ont été rejoués une fois avec les quotas inchangés : **Recall@5 100 %
(8 questions, 10 passages), complétude 7/8 (87,5 %), 15/15 références valides,
13/13 affirmations fidèles et couvertes, 2/2 abstentions, zéro erreur technique**.

H04 omet le rapport de huit pages maximum et l’affiche PDF, tout en ajoutant
une information de conservation correcte mais non demandée. Il est compté
comme incomplet. Tous les seuils chiffrés restent atteints ; aucune modification
de paramètres ne suit cette exécution. La variabilité du modèle demeure.

Il s’agit d’une **non-régression sur des cas déjà ouverts**, analysée par l’agent.
La validation humaine du porteur concerne le lot indépendant v5, pas cette
seconde exécution. Les deux résultats et le premier échec restent accessibles.

[Grille v7](non-regression-etape-8.md) ·
[Rapport v7](../evaluation/reports/quality-step8-v2-regression-v7.json) ·
[Réponses brutes v7](../evaluation/reports/answers-step8-final-v2-regression-v7.json).

## Latences et concurrence

Mesure HTTP depuis WSL vers l’URL publique, runtime `fra1`, backend 2 048 Mio /
1 CPU, E5 figé, corpus synthétiques, Groq `gpt-oss-120b`, budget 2 500 + 600 tokens.

- Recherche finale v7 : **30 requêtes**, p95 **353,11 ms**, maximum **14 690,04 ms**.
  Toutes réussissent ; les requêtes lentes restent dans le calcul. Deux recherches
  concurrentes réussissent en **324,07 et 522,51 ms**.
- Génération : **34 appels HTTP réussis cumulés**, p95 **12 234,71 ms**, maximum
  **18 418,49 ms**, abstentions explicites incluses. Le détail par prompt est publié.
  Ce cumul comprend plusieurs versions : il ne représente pas trente appels du
  seul prompt final. Le lot v7 contient dix appels réels, tous réussis.
- Les erreurs techniques sont comptées séparément. Les mesures du navigateur
  et les diagnostics locaux ne sont pas ajoutés à ce cumul HTTP.
- Les séries antérieures restent publiées : la v5 atteint un p95 de recherche
  de 15,43 s, avec deux encodages serveur de plus de 10 s. Des démarrages à froid
  sont probables ; l’état du modèle par requête n’a pas été instrumenté, donc
  aucune requête lente n’est retirée arbitrairement comme « froide ». La sonde
  dédiée ci-dessus mesure séparément un premier encodage avéré.

Les objectifs p95 < 2 s en recherche et < 20 s en génération sont observés sur
les séries décrites ; cela ne garantit pas cette latence à chaque démarrage ou
sur des documents plus longs. Les limites de concurrence et quotas s’appliquent.

[Synthèse reproductible](../evaluation/reports/latency-step8.json) ·
[Mesures finales de recherche](../evaluation/reports/performance-step8-v7.json).

## Clôture

Le contrôle final vérifie encore HTTPS public et une recherche E5 authentifiée
avec **zéro conteneur applicatif local actif**. Les services locaux sont ensuite
remis en route. Les données Preview/Production restent séparées et les secrets
restent hors dépôt. Le déploiement applicatif correspond au commit de code
indiqué plus haut ; la clôture Git ajoute les preuves et scripts de qualification
sans nouveau déploiement.

Au relevé du 13 octobre à 21:22 UTC : **48/50 tentatives Groq applicatives**
consommées, soit **2 restantes** globalement jusqu’au 14 octobre à 00:00 UTC
(**02:00 à Paris**). Aucun compteur n’est effacé et aucun plan payant activé.
La base Production occupe environ 9,4 Mio et les originaux environ 20,1 Mio.
