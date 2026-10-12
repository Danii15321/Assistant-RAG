# Corpus Iris pour Assistant RAG

Corpus original, fictif et francophone, version `iris-1`, consacré à un cours,
son parcours administratif et un laboratoire réseau. Aucun document personnel.
Les textes et annotations sont mis à disposition sous CC0-1.0.

## Fichiers et repères

`manifest.json` contient chemins, tailles, empreintes SHA-256 et résultats
d'import attendus. `reference_passages.json` donne 22 passages canoniques et leurs
repères : pages physiques PDF, paragraphes DOCX (titre inclus dans la numérotation),
lignes TXT. Ce sont des annotations de référence ; les chunks réels sont produits par le pipeline.

- PDF textuel de trois pages, DOCX et deux TXT : quatre documents exploitables.
- Deux politiques datées en contradiction ; la règle récente remplace l'ancienne.
- Instruction malveillante dans l'archive : elle doit rester une donnée.
- PDF corrompu, PDF constitué d'une image sans texte et TXT vide : trois refus attendus.

Les valeurs du cours fictif (220/40 tokens, seuil 0,78 et 12 Mio) servent à vérifier
les réponses. Elles ne sont pas la configuration de l'application.

## Annotations et évaluation

`questions.jsonl` contient 15 questions factuelles, 5 multi-passage, 5 hors corpus
et 5 suivis avec historique. Chaque ligne précise sélection, éléments attendus,
état et passages pertinents. La sélection `null` signifie toute la bibliothèque.
Q25 vérifie une sélection qui exclut la réponse présente dans un autre document.

Les 20 cas `development` servent aux essais. Les 10 cas `final` sont réservés
à la qualification ; le probe du cadrage ne les encode ni ne les évalue.
L'accès aux annotations par un auteur ne constitue pas une évaluation finale.
Ne pas ajuster paramètres, prompt ou seuil à partir des résultats finaux.

Pour la V1, relier les passages annotés aux chunks réellement extraits par leurs
repères et leur texte. Plusieurs chunks peuvent couvrir un même passage ; compter
chaque passage pertinent une seule fois. Évaluer ensuite génération et citations
avec la grille `expected_elements`, y compris contradiction et abstention.

Ce petit corpus synthétique fournit une vérification initiale. L'enrichir avec
documents autorisés plus longs avant de tirer des conclusions sur des cours réels.
Le probe de cadrage ne teste ni chunks 300/50, ni pgvector, ni isolation entre comptes.

## Reproduction

Depuis `/home/daniel/assistant-rag`, sous Ubuntu :

```bash
python3 -m venv /tmp/assistant-rag-step0-venv
/tmp/assistant-rag-step0-venv/bin/pip install --extra-index-url https://download.pytorch.org/whl/cpu -r scripts/step0/requirements.lock.txt
/tmp/assistant-rag-step0-venv/bin/python scripts/step0/check_corpus.py
/tmp/assistant-rag-step0-venv/bin/python scripts/step0/probe_embeddings.py
```

Les dépendances figent l'environnement d'essai Linux/Python 3.10, pas le futur
backend. Le premier lancement télécharge environ 449 Mio de poids dans le cache
Hugging Face hors dépôt. Aucun compte ni API d'embeddings payante n'est requis.

Les fixtures sont déjà présentes. Pour les reconstruire, exécuter
`scripts/step0/build_corpus.py` avec Python et les bibliothèques reportlab,
python-docx et Pillow, puis `scripts/step0/build_questions.py` et le contrôle.
La reconstruction des binaires peut modifier leurs empreintes à cause des dates
internes ; conserver ensemble fixtures et manifeste de la même génération.

## État des contrôles au 11 octobre 2026

Extraction des quatre documents, repères, empreintes, cas négatifs et annotations :
contrôlés. Les quatre pages PDF ont été rendues et inspectées visuellement.
Le contenu DOCX est vérifié par extraction ; le rendu visuel reste à contrôler :
le renderer disponible échoue parce que LibreOffice est absent sur ce poste.
Les images de contrôle temporaires sont exclues du dépôt.

Résultats CPU : [rapport JSON](reports/embeddings-step0.json).
Exécution réelle E5/Groq sur Vercel : [rapport froid/chaud](reports/vercel-step0.json),
[premier essai](reports/vercel-step0-initial.json),
[image et déploiement](reports/vercel-deployment-step0.json).
Le compte Groq est confirmé Free par le porteur. Les essais Vercel portent sur
deux passages fixes, sans évaluer le lot final ; voir le
[guide du prototype](../probes/vercel/README.md) pour les reproduire.
Interprétation, clôture de l'étape 0 et contrôles planifiés par étape :
[rapport de cadrage](../docs/etape-0-faisabilite.md).

## Récupération réelle : étape 5

```bash
python3 scripts/local/qualify_retrieval.py
```

Le script local prépare une base et un stockage d’évaluation isolés, réimporte
les quatre documents par le pipeline réel et relie les 22 annotations aux offsets
canoniques. Il encode uniquement les vingt cas `development`, avec les mêmes
conventions de sélection/historique que l’API, puis calibre le seuil sur une grille.
Il n’appelle aucun LLM et conserve les dix cas finaux sans les évaluer.

[Rapport de développement](reports/search-step5-development.json) : seuil **0,84**,
Recall@5 moyen **82,4 %** sur 17 questions répondables, 17 annotations pertinentes
couvertes sur 20 ; une question hors corpus sur trois n’a aucune correspondance.
La couverture exige l’annotation entière et ne compte pas deux fois les offsets
chevauchants. Deux questions sans réponse retrouvent encore du texte proche :
le seuil ne suffit pas à garantir une abstention correcte de l’assistant.

[Paramètres, méthode et limites](../docs/etape-5-recherche-locale.md).
Ces résultats sur cinq chunks synthétiques restent une mesure de développement,
sans validation finale, génération, fidélité de citations ni performance Vercel.

[Contrôles locaux](reports/search-step5-local.json) : 100 tests,
lint/types/build et parcours bureau/mobile. [Persistance](reports/search-step5-persistence.json) :
18 originaux/textes/index et résultats exacts inchangés après remplacement des
services. Les preuves des étapes précédentes restent des rapports historiques.

## Génération sourcée : étape 6

Le script `python3 scripts/local/qualify_answers.py --real --revalidate-retained`
évalue uniquement Q02, Q16 et Q21 sur le pipeline local réel et Groq Free.
Le journal garde trois réponses instrumentées ; une réponse reçue précédemment
peut être revalidée sans nouvel appel. Les erreurs d’exécution antérieures ne
sont pas comptées comme des abstentions ; un plafond de six appels est rapporté
pour l’étape, faute de nombre exact conservé pour le premier essai échoué.

[Essais réels](reports/answers-step6-groq.json) ·
[Revue de fidélité](reports/answers-step6-fidelity.json) : trois affirmations
étayées, trois références valides et une abstention correcte. La réponse Q16
reste partielle : elle cite les durées 45/30 jours mais omet de préciser
explicitement le remplacement daté. Complétude : **1 / 2 réponses**, pas une
qualification des objectifs V1 ni du lot final.

[Contrôles locaux](reports/answers-step6-local.json) : 130 tests, avec fournisseur
HTTP simulé pour le navigateur, aucun appel réel dans la suite ordinaire.
[Persistance](reports/answers-step6-persistence.json) : 26 documents/index/recherches
et compteurs conservés après remplacement des services.

## Conversations et reprise : étape 7

[Contrôles locaux](reports/conversations-step7-local.json) : **156 tests**,
avec 52 parcours Chromium sur bureau/mobile. Les conversations utilisent les
vrais comptes, l’API privée, PostgreSQL, l’indexation/recherche E5 et le fournisseur
HTTP synthétique. Le contrôle supplémentaire du formulaire après envoi inconnu
simule la réponse UI : son périmètre est la réinitialisation de l’accord et la
conservation de la sélection, pas le pipeline documentaire.

Le suivi de développement Q28 retrouve le chevauchement de **40 tokens** après
une question sur la taille de **220 tokens**, avec historique relu côté serveur.
Le suivi Oriole conserve le sujet et retrouve Lyon. Ces deux cas sont vérifiés
sur les deux profils ; aucune nouvelle mesure de fidélité Groq n’est annoncée.
Les dix cas finaux restent réservés. Aucun nouvel appel Groq réel ni déploiement.

[Persistance](reports/conversations-step7-persistence.json) : 36 documents,
16 conversations, 20 échanges et 10 sources inchangés après remplacement
PostgreSQL/API/worker, ainsi que les recherches et compteurs. Six sources gardent
leurs extraits ; les quatre supprimées n’en contiennent plus. Les deux autres
conversations vides proviennent du test de formulaire isolé.
[Parcours, décisions et limites](../docs/etape-7-conversations-locales.md).
