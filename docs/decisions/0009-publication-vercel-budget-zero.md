# ADR 0009 — Runtime Vercel et données durables

Date : 12 octobre 2026. Statut : implémenté, qualification en cours.

## Contexte

L’étape 8 publie l’application complète. Le prototype de l’étape 0 ne contient
ni comptes ni stockage durable. Le budget reste strictement nul.

## Choix

- Un projet Vercel Hobby `assistant-rag`, région `fra1`, deux Services : Next.js
  et FastAPI dans une image contenant E5 CPU à sa révision figée.
- Seul Next.js est exposé. Les bindings relient les services du même déploiement.
  FastAPI vérifie toujours le JWT et la session ; les opérations internes exigent
  un secret distinct de l’authentification utilisateur.
- Deux ressources Neon **Free**, deux stores Blob **privés**, secrets de session,
  de traitement et de cron distincts pour Preview et Production. Groq est activé
  uniquement en Production. Le local conserve ses volumes et sa configuration.
- Better Auth utilise PostgreSQL poolé. Le backend utilise l’endpoint direct,
  avec un petit pool SQLAlchemy : ses verrous consultatifs de session ne sont
  pas compatibles avec un pooler transactionnel. Aucun changement d’identité.
- Après réservation authentifiée, le serveur émet une URL PUT limitée à un UUID,
  un type MIME et une taille. Validité : neuf minutes, sans écrasement. Le navigateur
  envoie les octets directement à Blob sans cookie applicatif. La finalisation
  recalcule taille et SHA-256 côté serveur et vérifie la session de réservation.
- Les originaux restent dans Blob. Les fichiers de parsing sous `/tmp` sont
  bornés et supprimés en `finally`. Aucun téléchargement d’une URL client.
- PostgreSQL reste la source de vérité des travaux. Queues réveille un consommateur
  borné, avec les baux, checkpoints, verrous CPU et publications atomiques existants.
  Une invocation traite des lots pendant au plus 120 secondes avant un dernier lot
  borné. Queues réessaie lorsqu’il reste du travail, au plus 100 livraisons.
- La notification et la transaction SQL ne sont pas atomiques. La consultation
  d’un document en attente peut renvoyer un réveil, au plus une fois toutes les
  quinze secondes globalement ; un cron quotidien réconcilie les travaux et les
  objets orphelins. Une interruption entre commit et envoi reste donc récupérable,
  avec un délai pouvant atteindre un jour sans nouvelle visite.
- La recherche traite ses jobs E5 pendant la requête, sous le même verrou CPU.
  Aucun worker permanent, processus local distant ou traitement critique lancé
  après la réponse HTTP.

## Conséquences et limites

Services, Container et Queues restent des fonctionnalités bêta. Les offres
gratuites bloquent au quota ; la démonstration n’a pas de garantie de disponibilité.
Les imports sont plafonnés à 400 Mio globalement en Production et 100 Mio en
Preview, pour conserver une marge sous le quota Blob partagé. Les plafonds par
compte et le plafond de génération partagé restent appliqués.

Une URL d’envoi déjà émise reste utilisable jusqu’à son expiration après une
déconnexion. Elle ne permet ni lecture ni publication documentaire : la session
est revérifiée à la finalisation. Les uploads abandonnés et les objets tardifs
sont nettoyés par réconciliation ; la grâce d’une heure dépasse la validité du PUT.

Le dépôt GitHub conserve le code. La publication reste manuelle avec la CLI ;
aucune intégration Git ne déploie chaque commit pendant le développement.

## Sources officielles vérifiées

- [Services et tarification](https://vercel.com/docs/services/pricing)
- [Blob Hobby et blocage au quota](https://vercel.com/docs/vercel-blob/usage-and-pricing)
- [URLs Blob signées](https://vercel.com/docs/vercel-blob/vercel-signed-urls)
- [Queues et limites](https://vercel.com/docs/queues/pricing)
- [Neon Free](https://neon.com/pricing.md)
- [Compute Hobby](https://vercel.com/docs/functions/usage-and-pricing)
