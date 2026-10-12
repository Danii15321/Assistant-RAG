> Le choix GitHub ci-dessous est remplacé par [ADR 0003](0003-identifiants-locaux.md) ; le budget zéro reste obligatoire.

# Décision 0002 — Budget de 0 € et authentification

Date : 11 octobre 2026. Décision applicable à la V1 ; elle remplace les choix
de coût et d'identité de l'[ADR 0001](0001-groq-et-architecture-v1.md).

## Contexte et contrainte

Le porteur précise que le projet sert son CV et n'a aucun objectif commercial.
Le budget est **strictement de 0 €**, en développement et pour la démonstration
publique : LLM, embeddings, hébergement, identité, base, stockage et domaine.
L'authentification et Vercel restent obligatoires. Les services supplémentaires
sont intégrés au moment du besoin, selon la roadmap.

## Choix

- **Authentification : Better Auth open source dans Next.js, connexion GitHub
  OAuth.** Comptes, sessions et clés du plugin JWT résident dans Neon PostgreSQL.
  FastAPI vérifie les JWT du plugin via JWKS, puis applique les autorisations.
  Utiliser la bibliothèque et ses plugins ; aucune primitive d'authentification
  développée maison. Références : [Better Auth](https://better-auth.com/),
  [GitHub](https://better-auth.com/docs/authentication/github),
  [JWT pour services externes](https://better-auth.com/docs/plugins/jwt).
- **Inscription au premier accès GitHub**, connexion, déconnexion et expiration.
  La récupération du compte est gérée chez GitHub. L'application n'envoie aucun
  e-mail de vérification ou de réinitialisation et ne gère pas de mot de passe.
  L'e-mail n'est pas l'identifiant d'autorisation ; utiliser l'identité stable.
- **URL `*.vercel.app`**, HTTPS fourni par Vercel ; aucun achat de domaine.
  Enregistrer les callbacks de production et de développement dans des apps
  OAuth distinctes ; limiter les origines autorisées aux URLs contrôlées.
  [Configuration OAuth GitHub](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app).
- **Vercel Hobby** pour Next.js, FastAPI Container, Services et Queues, en restant
  dans les inclusions gratuites. La grille actuelle inclut **10 GB de stockage
  VCR** ; les deux images du prototype totalisent environ **1,35 GB**, hors autres
  usages du compte. Le tarif unitaire VCR ne constitue donc pas une dépense
  obligatoire pour ce prototype. Sources : [prix Vercel](https://vercel.com/pricing),
  [plan Hobby](https://vercel.com/docs/plans/hobby).
- **Neon Free**, PostgreSQL/pgvector, pour données métier et Better Auth. Les
  allocations publiées sont 1 GB de base et 100 CU-h/mois par projet ; vérifier
  le compte lors du provisionnement. [Offre Free Neon](https://neon.com/blog/neon-free-plan-1-gb-per-project).
- **Blob privé sur Hobby**, avec uploads directs autorisés. Cette offre bloque
  l'accès en cas de dépassement au lieu de facturer une consommation supplémentaire.
  [Règles Hobby Blob](https://vercel.com/docs/vercel-blob/usage-and-pricing).
- **Groq Free** et E5 CPU restent retenus, conformément aux essais déjà réussis.

## Règles d'exploitation à 0 €

- Aucun forfait payant, add-on payant, achat, essai temporaire nécessitant ensuite
  un abonnement, activation de facturation ou ajout de moyen de paiement.
- Vérifier le plan et les inclusions disponibles avant chaque provisionnement.
  Un Marketplace ne doit pas convertir implicitement le projet vers une offre payante.
- En cas de quota atteint, arrêter l'opération et afficher sa disponibilité
  ultérieure ; accepter suspension et démarrage à froid, sans montée de plan.
- Limites par compte/globales partagées entre instances ; surveiller CPU, mémoire,
  stockage, transferts, images et retries en incluant Preview et Production.
- Viser au plus 5 GB d'images VCR pour ce projet, garder les versions de rollback
  nécessaires et nettoyer les anciennes selon une politique documentée.
- Si une offre devient incompatible avec 0 €, adapter la charge ou remplacer le
  composant par une solution gratuite en conservant Vercel et l'authentification.

## Conséquences et validation

Clerk et le domaine acheté sont retirés du plan. L'inscription e-mail/mot de
passe était une proposition de cadrage ; elle est remplacée par GitHub OAuth
pour éviter une dépendance à l'envoi d'e-mails. Un compte GitHub est nécessaire
pour utiliser la bibliothèque privée ; l'accueil et la présentation restent publics.
Better Auth consomme une partie des ressources gratuites de la base et de Vercel.

L'étape 0 conserve ses preuves et son statut validé pour Groq/E5/Vercel. Le nouveau
parcours d'identité sera implémenté et testé à l'étape 2. Aucun fournisseur
d'identité ou service supplémentaire n'est provisionné par cette décision.
La livraison V1 exige aussi une démonstration publique fonctionnelle à **0 €**,
des quotas documentés et un comportement propre en cas de suspension.
