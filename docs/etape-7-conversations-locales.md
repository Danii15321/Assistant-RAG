# Étape 7 — Interface et conversations privées

Date : 12 octobre 2026. **Statut : validée en local.**

## Parcours disponible

Depuis [la bibliothèque locale](http://localhost:3000/library), ouvrir
« Mes conversations », puis « Nouvelle conversation ». Saisir la question,
choisir tous les documents prêts ou une sélection et accepter l’envoi du contexte
utile à Groq Free. Les échanges s’enregistrent dans PostgreSQL : question,
sélection, réponse ou abstention, dates et citations exactes consultables.

Recharger la page, se déconnecter puis se reconnecter permet de retrouver la
conversation sans régénérer les réponses. Les suivis recherchent à nouveau les
passages ; les dernières questions aident à comprendre le sujet, les anciennes
réponses ne servent pas de preuves documentaires. La recherche ponctuelle
`/search` conserve son usage sans historique enregistré.

La session expirée efface l’affichage privé et renvoie à la connexion.
Chaque échange dispose de références HTML propres pour éviter de confondre deux
citations `[S1]` dans une même conversation. Les textes sont échappés, sans HTML
ou Markdown arbitraire. Aucune donnée privée dans `localStorage`.

## Reprise, erreurs et suppressions

Un envoi a un UUID client stable. Le serveur retourne le même échange lors d’une
répétition réseau ; une autre question attend la fin de l’échange en cours.
Le rechargement affiche le traitement en cours et actualise son état. Après
210 secondes sans conclusion, la prochaine lecture marque un échec interrompu.
Aucun nouvel appel automatique ne reprend cet ancien envoi.

Une erreur LLM conserve la question et un état d’échec, avec une explication
lisible. Une tentative volontaire après résolution utilise un nouvel identifiant.
Une réponse hors corpus reste une abstention enregistrée ; une erreur technique
ne devient jamais une réponse documentaire. Les quotas partagés restent ceux
de l’étape 6, y compris après suppression d’une conversation.

Supprimer un document retire immédiatement les passages et extraits de ses
citations enregistrées et affiche « Source supprimée ». Les noms et repères
restent identifiables. Les questions et réponses peuvent encore contenir des
informations issues du document : supprimer aussi la conversation pour effacer
ces textes. La confirmation dans la liste efface ses échanges et citations.

Limites : 50 conversations par compte, 100 échanges par conversation, questions
jusqu’à 1 000 caractères et contexte relu d’au plus six messages. La recherche
utilise au plus deux questions précédentes de 500 caractères chacune. Aucun
service, abonnement ou appel payant nouveau.

## Vérification

Le parcours couvre navigateur → Better Auth → proxy privé → FastAPI → PostgreSQL
et E5 → fournisseur HTTP simulé → citations → reprise de l’historique.
Les contrôles attendus sont l’isolation avec deux comptes, les doubles envois,
la perte/révocation de session et les suppressions concurrentes, puis la
conservation des données après remplacement des conteneurs.

```bash
bash scripts/local/check.sh
# Après la suite navigateur, sur la seule base assistant_rag_test :
python3 scripts/local/verify_conversation_persistence.py
```

**156 tests passent** : quatre tests de configuration, 63 backend,
37 PostgreSQL et 52 Chromium sur bureau/mobile. Ruff/format, mypy, ESLint,
TypeScript et build de production passent. La revue React vérifie les pages
protégées, les annulations, les effets nettoyés, les libellés, les références
uniques, le texte échappé et la sélection conservée après récupération.
[Rapport technique](../evaluation/reports/conversations-step7-local.json).

Les [captures bureau](../evaluation/reports/step7-desktop.png) et
[mobile](../evaluation/reports/step7-mobile.png) ont été inspectées : question,
réponse, extrait exact, sélection et accord consultables, sans débordement.
La reprise d’une réponse réseau perdue utilise le pipeline réel ; le cas
supplémentaire de formulaire inconnu utilise une réponse UI simulée et vérifie
le même UUID, une seule insertion affichée, le texte vidé, l’accord décoché et
la sélection conservée.

Après recréation PostgreSQL/API/worker, **36 documents**, **16 conversations**,
**20 échanges**, **10 sources** et le compteur restant sont identiques.
Les six sources disponibles gardent leur contenu ; les quatre sources supprimées
n’ont plus de passage ni de citation textuelle. Les octets, textes, vecteurs et
recherches privées restent inchangés.
[Preuve de persistance](../evaluation/reports/conversations-step7-persistence.json).
Les corrections découvertes avant validation restent consignées dans
[l’observation initiale](../evaluation/reports/conversations-step7-initial.json) :
UUID sur HTTP, réponse 204 sans corps et réinitialisation de l’accord après
récupération. Les assertions ont échoué avant correction puis passent.
Le suivi Q28 du lot de développement demande le chevauchement après une question
sur la taille des passages de l’atelier Iris. E5 et PostgreSQL sont réels ;
les sorties 220/40 tokens viennent du fournisseur simulé. Ce contrôle vérifie
le parcours et la reprise, pas la fidélité de Groq sur toutes les questions.
Les limites de qualité mesurées à l’étape 6 restent applicables.

Contrôle final : `.env.local` et les sept fixtures restent inchangés ; aucune
valeur secrète trouvée dans 201 fichiers source et 27 bundles client. Les 80
liens documentaires locaux pointent vers des fichiers présents. `AGENTS.md`
reste à 270 lignes. L’application et l’API sont relancées et saines ; l’API
conversations renvoie `401` sans session. Les services isolés sont arrêtés.

## Migration et suite

[ADR 0008](decisions/0008-conversations-privees-et-reprise.md) décrit les tables,
le bail, l’idempotence et les snapshots effaçables. Migration additive
`0007_conversations`, sauvegarde privée locale avant application. Le downgrade
isolé vers `0006_generation` retire l’historique et ses triggers, en conservant
comptes, documents et compteurs ; il nécessite le code précédent.

Aucun nouveau déploiement Vercel et aucun appel Groq réel pour ces contrôles.
L’étape 8 reste la qualification finale et la préparation de la publication,
avec les dix cas réservés et la vérification des offres gratuites au jalon cloud.
