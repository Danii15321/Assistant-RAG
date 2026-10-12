# Étape 2 — Identité et isolation en local

Date : 11 octobre 2026. Statut : **validée en local**.
Choix confirmé : [ADR 0003](decisions/0003-identifiants-locaux.md).

## Parcours livré

- `/sign-up` : inscription avec `prenom.nom`, mot de passe et confirmation.
- `/sign-in` : connexion, nom normalisé en minuscules.
- `/library` : espace privé avec nom du compte et déconnexion ; import prévu à l’étape 3.
- Rechargement après expiration : retour à la connexion.

Aucun compte externe, identifiant OAuth ou adresse personnelle requis. Better Auth
1.7.7 gère le hachage scrypt et les sessions. Son adresse interne aléatoire sur
`accounts.invalid` reste technique, sans envoi ni fonction d’autorisation.
Aucune récupération automatique de mot de passe en V1.

## Frontières vérifiées

Le navigateur reçoit un cookie HttpOnly/SameSite Lax. Sa session dure 7 jours ;
Secure s’active avec une origine HTTPS. Les réponses ne livrent ni jeton ni
adresse interne à JavaScript ; aucun stockage de session dans localStorage.

Next.js vérifie la session en base. Son relais `/api/v1/*` émet un JWT uniquement
côté serveur. FastAPI valide EdDSA/Ed25519, clé d’un JWKS configuré, émetteur,
audience `assistant-rag-api`, expiration, sujet et identifiant de session. Il
vérifie aussi la session active en PostgreSQL : un JWT de 5 minutes est rejeté
immédiatement après déconnexion ou expiration de la session.

`users.id` est un UUID métier lié par FK à une identité SDK unique. Les routes
`GET /api/v1/users/me` et `GET /api/v1/users/{id}` illustrent le contrôle réutilisable :
aucun propriétaire choisi par le client ; autre compte et UUID absent donnent le
même 404. Liveness/readiness restent publiques. Les futures routes documentaires
réutiliseront cette dépendance et filtreront les propriétaires dans leurs requêtes.

Les POST d’authentification exigent l’origine exacte. Seules inscription par
username, connexion, déconnexion et lecture des clés publiques sont exposées.
Les opérations OAuth/e-mail, la lecture publique des sessions et l’émission
publique de JWT sont fermées. Corps borné à 4 Kio et erreurs neutralisées.
Les compteurs PostgreSQL sont partagés et globaux pour la petite démonstration :
5 inscriptions et 10 tentatives de connexion par minute. Changer un en-tête IP
ne permet pas de changer de compteur.

## Migrations et configuration

`0002_identity` applique le SQL généré/revu pour Better Auth 1.7.7 puis crée `users`.
Alembic reste l’unique propriétaire des migrations. Application, réapplication et
retour arrière sur base isolée sont couverts. Ne jamais rétrograder une base
contenant des comptes à conserver : le downgrade supprime les tables d’identité.

Le bootstrap complète `.env` sans écraser ses valeurs : origine locale, secret
Better Auth et secret de test distinct. Les tests utilisent `assistant_rag_test`
et deux serveurs internes séparés ; aucun compte fictif n’est créé dans la base
principale. Les clés privées JWT sont chiffrées par Better Auth en base.

Consulter le [guide local](developpement-local.md) pour lancement, contrôles,
synchronisation des modules Docker et précautions de rotation des secrets.

## Vérifications

**38 tests réussis :** 2 de configuration, 19 API/JWT, 3 PostgreSQL et 14 Chromium
(bureau/mobile). Ruff, format, mypy, ESLint, TypeScript strict et build passent.
La persistance du vecteur est conservée après recréation du conteneur PostgreSQL.
Les noms de 64 caractères sont couverts sans débordement sur mobile.

[Preuve structurée](../evaluation/reports/auth-step2.json) ·
[Capture bureau](../evaluation/reports/step2-desktop.png) ·
[Capture mobile, nom à la limite](../evaluation/reports/step2-max-username-mobile.png).

- Tests JWT et API : signatures modifiées, jetons non signés, émetteur/audience
  incorrects, expiration, claims invalides, anonymat, révocation et erreur neutralisée.
- PostgreSQL réel : migrations, recherche vectorielle conservée, deux propriétaires,
  UUID stable, FK et correspondance session/utilisateur.
- Chromium bureau/mobile sur build de production : inscription, connexion,
  déconnexion, cookie, bibliothèque privée, expiration, deux comptes et JWT révoqué,
  noms invalides/doublons, origines, chemins fermés et refus au quota d’authentification.
- Types stricts, lint, format et compilation ; persistance après recréation du conteneur DB.

Les essais sur serveur de développement ont rencontré des délais dus aux
compilations à la demande et à la pression mémoire WSL. Les tests ordinaires
utilisent désormais le build de production, avec les mêmes assertions.

## Limites et suite

Aucun déploiement Vercel, provisionnement Neon, appel Groq ou service payant.
L’HTTPS public, les cookies sur `vercel.app` et les connexions Neon seront qualifiés
au prochain jalon cloud demandé. L’authentification est certifiée ici en local.

La bibliothèque ne contient pas encore d’import ni de documents. L’étape 3 est
l’import privé et l’extraction PDF/DOCX/TXT. La récupération de compte reste une
intervention manuelle du porteur lorsqu’elle sera nécessaire.

L’audit npm de production et les alertes de développement sont consignés dans
[le rapport de dépendances](../evaluation/reports/auth-step2-dependency-audit.json).
L’audit npm de production compte **0 vulnérabilité**. La chaîne ESLint de l’étape 1 conserve ses cinq alertes de développement ; aucune
montée forcée de dépendance incompatible n’est appliquée.
