# Prototype de qualification Vercel — étape 0

Ce prototype FastAPI vérifie la faisabilité de **E5 CPU → recherche en mémoire →
Groq Free → contrôle de réponse et citation** sur Vercel Container. La fixture
contient deux passages fictifs et une question fixe. La V1, ses comptes,
documents, persistance et limiteurs distribués restent à développer.

## Déploiement vérifié

- Projet `assistant-rag`, espace `danii15321s-projects`, plan Hobby, région `fra1`.
- [Preview protégée](https://assistant-lkmtm142p-danii15321s-projects.vercel.app).
- [Inspection Vercel](https://vercel.com/danii15321s-projects/assistant-rag/CJPLW6bD9ExEQ4GD8ahZjtSdPLZt).
- [Contrôles froid/chaud](../../evaluation/reports/vercel-step0.json) et
  [métadonnées de l'image](../../evaluation/reports/vercel-deployment-step0.json).

`GET /` présente le prototype ; `GET /health` renvoie un état minimal.
`POST /probe` nécessite `Authorization: Bearer <STEP0_PROBE_TOKEN>` avant tout
encodage ou appel LLM. Aucun corps utilisateur n'est utilisé. La protection
Vercel est une barrière supplémentaire conservée sur la Preview ; elle redirige
les navigateurs sans session Vercel vers la connexion.

Les poids E5 sont téléchargés **pendant la construction**, avec révision figée.
Le runtime travaille hors ligne pour les embeddings, utilise un seul processus
et réutilise son encodeur. Seul l'appel Groq utilise un service d'inférence externe.
Le lockfile décrit l'environnement de qualification Linux/Python 3.10, pas le
futur backend ; il inclut aussi les dépendances des essais locaux.

## Secrets et reproduction sous Ubuntu

Depuis `/home/daniel/assistant-rag`, les variables `GROQ_API_KEY` et
`STEP0_PROBE_TOKEN` résident dans `.env.local`, ignoré et privé. Elles sont déjà
configurées en variables Vercel **Secret Preview**. Ne pas copier de clé dans
`.env.example`, le chat, les arguments CLI, les sources ou les rapports.

Le script `scripts/step0/configure_vercel_probe.py` vérifie le projet lié,
génère le jeton s'il manque et transmet les secrets à la CLI via stdin.
Il est destiné au provisionnement initial, pas à une réexécution systématique.

```bash
cd /home/daniel/assistant-rag
# Contrats d'accès, fournisseur simulé : aucun appel Groq.
/tmp/assistant-rag-step0-venv/bin/python -m pytest probes/vercel/test_probe.py -q
# Construction de l'image avec poids embarqués :
docker build -f probes/vercel/Dockerfile.vercel -t assistant-rag-step0:local probes/vercel
# Projet lié et session CLI vérifiés ; toujours préciser Preview.
npx --yes vercel@63.1.2 deploy --target preview --yes --scope danii15321s-projects --project prj_YRjALOFSlBmLPqv4n3cJa1CRSV0W
# Remplacer l'URL si un nouveau déploiement a été créé.
python3 scripts/step0/verify_vercel_probe.py https://assistant-lkmtm142p-danii15321s-projects.vercel.app
python3 scripts/step0/record_vercel_evidence.py
```

Le dernier script cible explicitement le déploiement qualifié initial. L'adapter
au nouvel ID avant de consigner les métadonnées d'un autre déploiement.
Le vérificateur utilise `vercel curl` pour accéder à la Preview protégée du projet
lié et un fichier d'en-tête temporaire privé pour le jeton applicatif. Il s'arrête
au premier échec et effectue **deux appels réels Groq** en cas de succès.
Les rapports exposent uniquement mesures, usage, contrôles et empreintes.

## Portée des mesures

Premier chargement du second essai : 8,684 s ; total applicatif : 9,313 s.
Invocation suivante avec modèle chargé : 0,435 s ; pic RSS : 869,6 Mio.
Les temps excluent le démarrage du conteneur, le réseau entrant et la CLI.
La fixture courte ne qualifie pas les lots de 300 tokens, les imports, les quotas
distribués, la concurrence, PostgreSQL, Blob, Queues ou les parcours d'identité.
Le niveau Groq Free est confirmé par le porteur dans Billing ; la facture
d'infrastructure Vercel/VCR n'a pas été certifiée par ces essais. La contrainte
actuelle est un budget de 0 € : le projet reste sur Hobby et ses inclusions,
avec 10 GB de stockage VCR publiés et environ 1,35 GB pour les deux images.
Voir l'[ADR 0002](../../docs/decisions/0002-budget-zero-et-authentification.md).
