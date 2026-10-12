# Décision 0001 — Groq et architecture de la V1

Date : 11 octobre 2026. Cadrage validé ; contrôles complémentaires planifiés par étape.
Références : [spécification](../specification.md),
[preuves et budget](../etape-0-faisabilite.md).
Les choix de coût et d'identité sont révisés par l'[ADR 0002 — budget zéro](0002-budget-zero-et-authentification.md),
qui fait foi depuis la précision du porteur : projet CV non commercial à 0 €.
Le choix d'identité actuel est précisé par l'[ADR 0003](0003-identifiants-locaux.md).

## Contexte

Le porteur confirme une API LLM gratuite, une authentification et un hébergement
public sur Vercel dès la V1. Il retient la solution Groq Free proposée et confirme
le niveau Free dans Billing. Une clé privée est configurée et le projet
`assistant-rag` a été créé dans son espace Vercel Hobby. Les appels réels local
et Vercel ont réussi ; les rapports ne contiennent aucun secret.

## Choix

- Génération : **Groq Free**, `openai/gpt-oss-120b`, appel direct depuis FastAPI,
  adaptateur remplaçable, sans outil externe, sans passerelle payante et sans fallback
  payant. Rester sur Free ; accès réel confirmé, en-têtes observés :
  1 000 requêtes/jour et 8 000 tokens/minute. Les limites sont à surveiller.
- Embeddings : **intfloat/multilingual-e5-small**, révision
  `614241f622f53c4eeff9890bdc4f31cfecc418b3`, CPU, 384 dimensions, vecteurs
  normalisés, préfixes `query: ` et `passage: `. Découpage cible 300/50 tokens du
  tokenizer E5 ; aucun passage ne dépasse 512 tokens, préfixe et tokens spéciaux inclus.
- Recherche : pgvector, cosine, top-k 5 ; recherche exacte filtrée au départ.
  Le seuil d'abstention reste à calibrer sur le lot de développement à l'étape 5.
- Vercel Services : Next.js et FastAPI dans un projet ; **Container** pour Python,
  modèle téléchargé à la construction et embarqué dans l'image. Pas de téléchargement
  de modèle lors d'une requête ni de dépendance à la machine locale en production.
- Persistance : **Neon PostgreSQL + pgvector**, connexion poolée ; Blob **privé**
  pour les originaux, uploads directs autorisés ; Vercel Queues pour l'ingestion.
  Tous ces services restent à provisionner et qualifier sur le compte réel.
- Identité : **Better Auth + `prenom.nom` / mot de passe**, conformément à l'ADR 0003.
  Sessions dans Neon Free, JWT/JWKS pour FastAPI, URL `vercel.app` sans domaine
  acheté. Aucun e-mail personnel ni fournisseur OAuth requis.
- Pilote personnel non commercial : Vercel Hobby, régions applicative et base
  proches (Preview FastAPI confirmée à Frankfurt `fra1`). Environnements
  séparés ; Preview ne contient que des données synthétiques.

## Options considérées

Gemini n'est pas retenu selon la préférence du porteur. OpenRouter et Cloudflare
ne sont pas ajoutés comme fournisseurs automatiques : multiplier les adaptateurs
n'est pas nécessaire au prototype. E5 small réduit le poids par rapport à un
modèle multilingue plus grand et a réussi un premier essai CPU en français.

Le runtime Python standard est écarté pour cette combinaison : l'environnement
d'essai pèse environ 1,4 Gio avant les poids E5 d'environ 449 Mio, alors que la
limite standard documentée est 500 MB. L'image OCI du prototype est déployée :
672 534 414 octets compressés, E5 exécuté en `fra1`, recherche et génération
sourcée réussies. Cela qualifie cette fixture courte, pas l'ingestion complète.

Clerk avait été proposé pour ses parcours gérés. L'exigence nouvelle de 0 €
retire ce choix et le domaine acheté du plan. GitHub OAuth avait ensuite été
proposé ; le porteur a choisi des identifiants locaux, sans envoi d'e-mails.

## Conséquences et portes de validation

Les quotas Free limitent une démonstration publique : plafonds par compte et
globaux persistés, budget de tokens, concurrence bornée, erreurs explicites.
Les embeddings n'ont pas de coût API, mais consomment CPU et mémoire Vercel.
Container, Services, Queues et VCR sont des fonctionnalités bêta à vérifier.
Le projet reste sur les offres gratuites, y compris VCR dans ses inclusions
Hobby. Aucun domaine acheté ni montée de plan ; suspendre les opérations au
quota. La vérification de budget détaillée et les sources figurent dans l'ADR 0002.

Services, Container et VCR ont fonctionné sur le compte Hobby réel. Les secrets
Groq et du probe sont configurés exclusivement en Preview ; la protection Vercel
est conservée. Le prototype n'implémente pas les comptes utilisateur de la V1.

Le 11 octobre 2026, le porteur approuve la clôture de l'étape 0 sur les preuves
disponibles : cadrage, corpus initial, appels réels Groq Free et Preview Vercel
exécutant FastAPI, E5, recherche et génération sourcée sur une fixture synthétique.
Il demande de traiter les autres contrôles quand le besoin se présente.

La base/pgvector est qualifiée à l'étape 1 ; l'identité à l'étape 2 ; Blob privé,
upload et consommateur durable à l'étape 3 ; les lots d'embeddings à l'étape 4 ;
la production et le budget réel à l'étape 8. Vérifier les coûts et quotas d'un
service au moment de son provisionnement. Ces contrôles n'empêchent plus la
clôture de l'étape 0. En cas d'échec à l'étape concernée, adapter fournisseur,
modèle, lots ou périmètre gratuit en conservant les exigences d'authentification
et de Vercel, sans montée vers un plan payant.

À la demande du porteur le même jour, l'étape 1 et les développements suivants
sont testés en local. Les services managés et essais cloud mentionnés ci-dessus
seront regroupés à un jalon Vercel ultérieur ; aucun déploiement à chaque
implémentation. La publication publique de la V1 reste obligatoire.
