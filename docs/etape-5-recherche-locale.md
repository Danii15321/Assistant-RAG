# Étape 5 — Recherche privée locale

**Validée en local le 11 octobre 2026.** Budget : **0 €**, aucun appel
LLM, déploiement ou provisionnement cloud.

## Parcours et contrat

Depuis la bibliothèque, ouvrir « Rechercher dans mes documents », saisir une
question et rechercher dans tous ses documents prêts ou une sélection explicite.
Les résultats présentent fichier, repères physiques, score et texte exact dans
« Lire le passage ». Aucun contenu n’est mis dans `localStorage` ni un cache public.

`POST /api/v1/search` reçoit `question`, `document_ids` (`null` = tous les prêts),
`top_k` (5 par défaut, 1 à 10) et un historique optionnel borné. Une liste vide
est refusée, un UUID étranger/inexistant produit la même 404, un document non
prêt/incompatible une 409. La sélection n’est jamais élargie silencieusement.

La réponse distingue `matches`, `no_match` et `empty_corpus`. Elle contient les
passages exacts, scores, repères, compte de tokens, versions et durée. L’identité
du passage est le triplet document/génération/ordre. Les vecteurs ne sont pas
exposés. Une session expirée/révoquée produit une 401, une file occupée une 429,
un timeout ou une erreur d’encodage une 503 ; ce ne sont pas des « no_match ».

## Paramètres et isolation

| Paramètre | Valeur |
| --- | --- |
| Modèle / index | E5 small et configuration de l’étape 4, 384 dimensions |
| Encodage question | Préfixe `query: `, CPU, L2, maximum 512 tokens complets |
| Question / historique | 1 000 caractères / quatre messages de 500 caractères |
| Suivis | Deux dernières questions utilisateur ; réponses assistant ignorées |
| Classement | Distance cosinus exacte, propriétaire/sélection filtrés avant classement |
| Candidats / top-k | 50 / 5 par défaut, maximum demandé 10 |
| Seuil | 0,84, configurable côté serveur par `SEARCH_THRESHOLD` |
| Contexte | Au maximum 1 500 tokens de passages |
| Déduplication | Texte identique ; chevauchement ≥ 80 % du passage le plus court |
| File CPU | Un travail par compte, huit globalement, même worker que l’ingestion |
| Bail / expiration | 120 / 130 secondes |
| Attente API / proxy / client | 105 / 115 / 120 secondes |

Le SQL matérialise les seuls passages autorisés, prêts, compatibles et de la
génération publiée. Pour une sélection explicite, un verrou partagé protège
la vérification et le classement dans une même transaction. Les baux protègent
les résultats d’encodage contre une réponse ancienne ou une session révoquée.
Un verrou de session PostgreSQL est détenu pendant le cycle du worker ;
l’annulation du travail ou la suppression de la session ne libère pas le CPU
avant la fin du calcul. Il est libéré même lors d’une exception, avant restitution
de la connexion au pool.

La file stocke temporairement la question dans PostgreSQL local. Le calcul en
efface le texte ; l’API supprime le travail après consommation ou erreur. Un
travail expiré est inexploitable et purgé au prochain cycle du worker ou à sa
reprise. Aucun historique de recherche n’est créé à cette étape.

Les conventions suivent la [documentation pgvector](https://github.com/pgvector/pgvector)
et les paramètres E5 déjà qualifiés à l’étape 4. [ADR 0006](decisions/0006-recherche-privee-et-seuil.md).

## Évaluation réellement exécutée

[Rapport de développement](../evaluation/reports/search-step5-development.json).
Quatre fichiers Iris réimportés/extraits/indexés par le pipeline réel dans la
base locale isolée `assistant_rag_evaluation`, cinq chunks et 22 annotations
reliées au texte exact avec leurs repères physiques. Les cas finaux ne sont pas
encodés ni évalués. Les essais ne consomment aucun LLM ni API d’embeddings.

| Mesure | Résultat |
| --- | --- |
| Cas de développement | 20 : 17 répondables et 3 hors corpus |
| Recall@5 moyen par question répondable | **82,4 %** |
| Annotations pertinentes couvertes | **17 / 20** |
| Questions hors corpus sans correspondance | **1 / 3** |
| Indexation réelle du corpus | 59,297 s |
| Recherche chaude, E5 + SQL, 20 observations | Médiane 0,063 s ; p95 0,111 s |
| Cas finaux exécutés | **0 / 10** |

Le rappel exige la couverture entière d’une annotation par l’union des offsets
des passages retenus ; le chevauchement ne donne pas de double crédit. Les
suivis utilisent les mêmes conventions d’historique que l’API. La grille et
chaque cas de développement sont publiés dans le rapport.

L’objectif local de Recall@5 ≥ 80 % est atteint sur ce petit corpus synthétique.
Le score ne détecte pas systématiquement une information absente dans un texte
proche : deux questions hors corpus récupèrent encore des passages. Cela reste
à traiter avec les contrôles de génération/abstention de l’étape 6. Ces mesures
ne valent pas une qualification sur documents réels ni sur Vercel.

## Vérifications techniques

Les tests couvrent la sélection et le filtrage avant classement, les scores
cosinus réels, les budgets, les suivis sans preuve provenant de l’assistant,
les limites partagées, les baux remplacés, les délais et la révocation de session.
Le verrou CPU est vérifié avec deux connexions PostgreSQL, même après suppression
du travail et de la session ; sa libération après exception est contrôlée.

La revue React vérifie les frontières serveur/client, les effets nettoyés,
l’annulation, les clés stables, les libellés et contrôles HTML accessibles,
l’absence d’injection HTML et de contenu privé dans le stockage navigateur.
Les captures [bureau](../evaluation/reports/step5-desktop.png) et
[mobile](../evaluation/reports/step5-mobile.png) montrent les passages ouverts sans débordement.

**100 tests passent** : 2 bootstrap, 48 backend, 24 PostgreSQL et 26 Chromium
(bureau/mobile). Ruff/format, mypy, ESLint, TypeScript et build Next.js passent.
L’import réel des trois formats et l’envoi direct de 20 Mio restent validés.
[Rapport technique](../evaluation/reports/search-step5-local.json).

Après recréation de PostgreSQL puis remplacement API/worker, les **18 documents**
de test conservent leurs originaux, unités canoniques, vecteurs et résultats
exacts de recherche privée : [preuve de persistance](../evaluation/reports/search-step5-persistence.json).
Les rapports historiques de l’étape 4 restent conservés.

## Reproduction, migration et suite

```bash
bash scripts/local/check.sh
python3 scripts/local/qualify_retrieval.py
```

Les scripts exécutent les charges séquentiellement, arrêtent temporairement les
frontends/workers inutilisés et relancent les services de développement à leur
sortie. Le second script crée uniquement la base et le volume d’évaluation locaux.
Les documents et le compte synthétique de son exécution sont nettoyés à la fin.
Il ne touche ni aux comptes/documents de développement ni aux dix cas finaux.

Migration additive `0005_search` : ajoute seulement la file éphémère. Une
sauvegarde locale précède son application. Le downgrade supprime cette file,
sans modifier les comptes, originaux ou index publiés ; remettre le code de
l’étape 4 avec ce schéma. Le rollback est testé uniquement sur base isolée.

L’étape 6 ajoutera les réponses sourcées, les références et l’abstention. La
qualification Vercel reste regroupée à un jalon ultérieur ; aucun déploiement
automatique n’est effectué.
