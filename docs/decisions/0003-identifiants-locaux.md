# ADR 0003 — Authentification par nom d’utilisateur et mot de passe

Date : 11 octobre 2026. Statut : accepté, demandé par le porteur.
Remplace le choix GitHub d’ADR 0002 ; conserve son budget strict de 0 €.

## Contexte et décision

Le porteur souhaite `prenom.nom` / mot de passe, sans compte GitHub ni configuration
OAuth. Better Auth reste le SDK : hachage scrypt, cookies et sessions sont gérés par
la bibliothèque. Son plugin username valide et normalise les noms uniques.
Aucun fournisseur d’identité, abonnement, e-mail ou service cloud nouveau.

L’inscription reçoit uniquement un nom et un mot de passe. Le SDK exige une adresse
interne : le serveur génère un UUID sur `accounts.invalid`. Cette adresse ne sert
ni à contacter l’utilisateur ni à déterminer le propriétaire de ses documents.
Les routes e-mail/OAuth inutiles et l’émission publique de jetons sont fermées.

## Frontière et persistance

Next.js vérifie le cookie avec la base, puis émet côté serveur un JWT EdDSA de
5 minutes, audience `assistant-rag-api`. FastAPI vérifie signature, émetteur,
audience, expiration et correspondance `sid`/`sub` avec une session active en base.
Une déconnexion révoque ainsi immédiatement même un JWT non expiré.
Les UUID métier sont distincts des identifiants du SDK, avec FK et unicité.
Alembic possède les migrations, y compris les tables SDK générées pour 1.7.7.

Cookies HttpOnly/SameSite Lax, Secure lorsque l’origine est HTTPS ; sessions de
7 jours sans cache empêchant la révocation. Aucune session ou clé dans localStorage.
La limitation des tentatives utilise PostgreSQL et un compteur global, sans
confiance dans les IP envoyées par les clients. Cette limite favorise la simplicité
pour la petite démonstration CV ; la qualification publique vérifiera ses quotas.

## Conséquences et limites

Les essais locaux peuvent couvrir toute la connexion sans identifiants externes.
Il n’y a pas de récupération automatique de mot de passe dans la V1 sans e-mail.
En cas de perte, une intervention manuelle du porteur sera nécessaire ; aucun
contournement public ou question secrète. Une évolution éventuelle sera cadrée
lorsque le besoin se présentera.

Origines, HTTPS, cookies et base Neon seront qualifiés ensemble au prochain jalon
Vercel demandé ; aucun déploiement ne fait partie de cette étape locale.

## Références

- [Plugin username](https://better-auth.com/docs/plugins/username)
- [Mots de passe Better Auth](https://better-auth.com/docs/authentication/email-password)
- [JWT/JWKS](https://better-auth.com/docs/plugins/jwt)
- [Sessions](https://better-auth.com/docs/concepts/session-management)
