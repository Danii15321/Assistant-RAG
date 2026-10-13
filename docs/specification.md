# Spécification du projet My Talking RAG — V1

- **Date :** 13 octobre 2026.
- **Référence :** [README du projet](../README.md).
- **Statut :** étapes 0 à 8 achevées ; application publique sur Vercel, appels Groq réels et contrôles d’exploitation vérifiés. Le nouveau lot réservé obtient 100 % de Recall@5, 8/8 réponses complètes et 2/2 abstentions. Le porteur a validé la grille de qualité le 13 octobre 2026. Voir [le rapport de publication](etape-8-publication.md) pour les contrôles, les incidents conservés et les limites. La non-régression finale v7 obtient 7/8 réponses complètes, 15/15 références valides et 2/2 abstentions.
- **Convention :** les exigences du README et les demandes explicites du porteur de projet sont obligatoires. Les décisions sont consignées dans [ADR 0001](decisions/0001-groq-et-architecture-v1.md) et [ADR 0002 — budget zéro](decisions/0002-budget-zero-et-authentification.md), pour le budget, et [ADR 0003 — identifiants locaux](decisions/0003-identifiants-locaux.md) pour l’identité actuelle ; une décision ne prouve pas sa validation en production.
- **Périmètre confirmé :** authentification et hébergement public sur Vercel dès la V1, avec des données privées par utilisateur.
- **Budget et finalité :** **0 €** pour le développement et la démonstration publique, tous services compris ; projet personnel destiné au CV, sans objectif commercial. Offres gratuites uniquement et URL `vercel.app`.

## 1. Vision et objectifs

Construire un assistant permettant à un utilisateur d'importer ses documents, de poser des questions en langage naturel et de recevoir des réponses fondées sur leur contenu, avec des citations consultables.

Le cas d'usage de référence est un étudiant important ses cours, ses supports PDF et ses notes. Il interroge cette base et retrouve les passages qui justifient les réponses.

La V1 doit démontrer la chaîne RAG complète : import → extraction → découpage → embeddings → indexation → recherche → génération avec sources → historique → évaluation.

### Résultats attendus

- Importer et indexer les fichiers PDF, DOCX et TXT exploitables.
- Rechercher les passages pertinents dans les documents sélectionnés.
- Produire des réponses accompagnées de citations vérifiables.
- Signaler un manque d'information plutôt qu'inventer une réponse.
- Conserver les conversations après rechargement et redémarrage.
- Mesurer séparément la recherche, les réponses et les citations.
- Utiliser une API LLM gratuite, dans les limites de son offre.
- Permettre l'inscription, la connexion et la déconnexion avec une session sécurisée.
- Livrer une application publique en HTTPS sur Vercel avec des bibliothèques privées par utilisateur.
- Démontrer ces fonctionnalités sans dépense ni abonnement payant ; gérer les limites des offres gratuites.

## 2. Périmètre de la V1

### 2.1 Exigences du README

| ID  | Fonctionnalité obligatoire           | Résultat observable |
| --- | ---                                  | ---                                                               |
| F01 | Import PDF, DOCX et TXT              | Un fichier valide apparaît dans la bibliothèque avec son état. |
| F02 | Extraction et découpage              | Du texte et des passages localisables sont conservés. |
| F03 | Embeddings et indexation vectorielle | Les passages disposent de vecteurs dans PostgreSQL avec pgvector. |
| F04 | Recherche sémantique                 | Une question retrouve les passages pertinents de la base. |
| F05 | Génération avec citations            | La réponse renvoie aux passages réellement récupérés. |
| F06 | Historique des conversations         | Une conversation peut être créée, consultée et reprise. |
| F07 | Jeu de tests de pertinence           | Un rapport reproductible présente les métriques et les échecs. |

### Exigences complémentaires confirmées

| ID | Fonctionnalité obligatoire | Résultat observable |
| --- | --- | --- |
| F08 | Authentification et autorisation | Un utilisateur accède uniquement à ses documents, conversations et sources. |
| F09 | Hébergement public sur Vercel | Une URL HTTPS de production permet le parcours complet sans machine locale en fonctionnement. |

### 2.2 Choix proposés

- Application publique sur Vercel, avec plusieurs comptes et une bibliothèque privée par utilisateur ; Docker reste utilisé pour le développement local.
- Interface en français ; évaluation prioritaire sur des documents et questions en français.
- Recherche dans les documents prêts du compte connecté ou dans une sélection explicite lui appartenant.
- Import d'un fichier par requête ; l'interface peut enchaîner plusieurs imports.
- Imports traités par des fonctions Python déclenchées par Vercel Queues ; états et progression persistés dans PostgreSQL.
- En production, fichiers dans Vercel Blob privé et métadonnées, textes et vecteurs dans PostgreSQL/pgvector managé ; adaptateur de stockage local pour le développement.
- Réponses complètes en une fois ; streaming reporté.
- Suppression de documents et de conversations, et relance des imports échoués.

Ces choix complètent le README et pourront être révisés pendant le cadrage.

### 2.3 Hors périmètre

Partage entre comptes, organisations et rôles avancés, OCR, analyse des images et schémas, interprétation avancée des tableaux complexes, connecteurs externes, recherche web, fine-tuning, agents autonomes, facturation et haute disponibilité.

Les PDF sans couche textuelle sont refusés avec une explication. Les pages non exploitables d'un PDF mixte sont signalées. Les DOCX et TXT utilisent des repères de paragraphes ou de lignes, sans pagination artificielle présentée comme celle du fichier original.

## 3. Parcours utilisateur

### S'inscrire et se connecter

1. Consulter la page publique et ouvrir l'inscription ou la connexion.
2. Créer son compte avec `prenom.nom` et un mot de passe, ou se connecter avec ses identifiants.
3. Arriver directement dans le chat : nouvelle question au centre, conversations dans la barre latérale et accès à la bibliothèque.
4. Se déconnecter ; les routes métier redeviennent inaccessibles.
5. Une session expirée ramène à la connexion. Aucune récupération automatique de mot de passe dans la V1 ; intervention manuelle du porteur si nécessaire.

### Importer

1. Cliquer sur « + » dans le chat et sélectionner un ou plusieurs fichiers ; l’envoi démarre directement. La bibliothèque conserve aussi son formulaire d’import.
2. Une session authentifiée autorise un upload direct vers le stockage privé ; le serveur vérifie l'objet reçu et crée le travail d'indexation.
3. L'interface affiche l'état : en attente, en cours, prêt ou en erreur.
4. Les états se mettent à jour dans le chat. Le brouillon reste conservé pendant la préparation ; l’envoi de la question attend la fin des traitements en cours. Seuls les documents prêts sont sélectionnables.
5. Un fichier invalide est signalé sans interrompre les suivants. En cas d’échec de traitement, proposer de consulter la bibliothèque pour le relancer.

### Questionner et vérifier

1. Écrire directement une question dans l’écran de chat ; la conversation est créée au premier envoi. Retrouver les conversations existantes dans la barre latérale.
2. Consulter tous les documents prêts par défaut ou ouvrir « Documents à consulter » pour une sélection. Confirmer l’envoi du contexte utile à Groq pour cette réponse, puis envoyer avec Entrée ou la flèche. Maj + Entrée ajoute une ligne.
3. Récupérer les passages pertinents, puis générer la réponse.
4. Afficher la réponse et les citations.
5. Au clic sur une citation, afficher le fichier, le repère et l'extrait exact.
6. Distinguer explicitement manque d'information et erreur du service LLM.

### Apparence et sources (évolution locale du 14 octobre 2026)

- L’identité publique devient **My Talking RAG**, avec un symbole original à deux rubans de citation entrelacés.
- Les sources se présentent en cartes sous la réponse : nom réel du fichier,
  repère PDF/DOCX/TXT et citation exacte. Le clic sur une carte ou une référence
  ouvre un panneau avec les extraits cités et le passage complet. Le lien vers
  le document ouvre le texte extrait privé ; aucune URL publique n’est créée.
- Les sources supprimées restent signalées, sans extrait ni lien vers le fichier.
- La bibliothèque permet de filtrer par nom et format pris en charge. Aucune
  date ni métadonnée absente de l’API n’est fabriquée pour reproduire la maquette.
- Paramètres : apparence et volet dépliable de confidentialité.
  Clair, Sombre et Système sont mémorisés par un cookie de préférence d’un an,
  distinct des sessions ; Système est le choix initial et suit l’OS via CSS.
- Barre d’icônes repliée par défaut : le logo ouvre le panneau latéral et son historique.
  Nouvelle discussion, Documents et Paramètres restent accessibles en mode compact,
  avec des libellés au survol/focus. Aucun badge ni texte de bandeau supérieur.
- Accueil minimal : « Par où commence-t-on ? », saisie, import +, périmètre, état
  et consentement explicite. Aucun slogan ni suggestion décorative. Les autres
  pages privilégient les actions, avec les explications secondaires dépliables.
- Navigation au clavier, fermeture par Échap et retour du focus pour le panneau.
  L’affichage fonctionne sur bureau et mobile. Aucun choix de LLM ni curseur de
  recherche ne sont ajoutés. Cette évolution n’est pas encore déployée.

### Reprendre

Retrouver les échanges persistés et poursuivre la discussion. Une question de suivi utilise un historique borné, mais les faits de la nouvelle réponse doivent être justifiés par une nouvelle recherche documentaire.

## 4. Spécifications fonctionnelles

### 4.0 Authentification et isolation des comptes

**Choix confirmé : Better Auth open source avec nom d’utilisateur `prenom.nom` et mot de passe**, dans Next.js et PostgreSQL local ; Neon Free sera qualifié au jalon Vercel. Aucun compte externe ni service d’e-mails. Voir [ADR 0003](decisions/0003-identifiants-locaux.md).

- Inscription explicite, connexion, déconnexion et expiration. Le nom est normalisé en minuscules, sans accents, avec chiffres/traits d’union admis de part et d’autre du point ; 3 à 64 caractères. Mot de passe de 12 à 128 caractères, haché par Better Auth.
- Aucune adresse personnelle demandée. L’adresse interne technique requise par le SDK est aléatoire, sur `accounts.invalid`, sans envoi ni rôle dans l’autorisation.
- Accueil, inscription et connexion publics ; bibliothèque, chat et API métier protégés.
- Session de 7 jours, cookie `HttpOnly`, `SameSite=Lax`, `Secure` en HTTPS ; aucun jeton dans `localStorage`. Pas de cache de session qui retarderait une révocation.
- Next.js vérifie la session en base et émet un JWT uniquement côté serveur pour joindre FastAPI. JWT EdDSA/Ed25519 de 5 minutes : `sub`, `sid`, émetteur et audience `assistant-rag-api`. FastAPI vérifie indépendamment signature via JWKS de confiance, algorithme, claims et session encore active en base ; une déconnexion invalide immédiatement les JWT associés.
- Le propriétaire UUID applicatif provient exclusivement de l’identité vérifiée. Toutes les futures lectures/écritures sont filtrées par propriétaire côté serveur et en SQL. Un UUID inconnu ou appartenant à autrui reçoit le même `404` ; session invalide/expirée : `401`.
- Better Auth possède ses tables dédiées, Alembic applique leurs migrations ; aucune primitive de mot de passe/session réimplémentée.
- Origine exacte obligatoire sur les opérations à cookie. Limites partagées PostgreSQL, globales pour cette petite démonstration : 5 inscriptions et 10 tentatives de connexion par minute, sans confiance dans un en-tête IP fourni par le client. Les autres routes OAuth/e-mail et l’émission publique de JWT restent fermées.
- Aucun cache public ou partagé entre comptes pour les données privées.
- La récupération automatique de mot de passe n’est pas livrée dans cette V1 sans e-mail. Un compte perdu nécessite une intervention manuelle du porteur ; ne pas demander de mot de passe dans le chat, ne pas implémenter de question secrète ni de contournement public.

### 4.1 Import et gestion documentaire

- Accepter PDF avec texte extractible, DOCX non chiffré et TXT UTF-8, avec ou sans BOM.
- Limite initiale proposée : **20 Mio par fichier**, configurable.
- Vérifier extension, type déclaré et structure réelle ; le nom seul ne suffit pas.
- Attribuer un UUID et une clé de stockage liée au propriétaire ; conserver le nom original comme métadonnée. Fichiers privés, sans URL publique permanente.
- Calculer une empreinte SHA-256 côté serveur et dédupliquer uniquement dans la bibliothèque du propriétaire, sans révéler les fichiers des autres comptes ; un document échoué peut être relancé.
- États : `uploading`, `queued`, `processing`, `ready`, `failed`, `deleting`.
- Seuls les documents `ready` sont recherchables.
- Conserver un code d’erreur stable et afficher sa description lisible sans trace interne.
- Traiter proprement les fichiers corrompus, chiffrés, vides ou trop volumineux.
- Limiter aussi la taille décompressée des DOCX, le texte extrait et le temps d'extraction.

En production, conserver la limite applicative de 20 Mio par un upload direct navigateur → Blob privé, autorisé par un jeton court limité à un objet, une taille et des formats. Les octets ne transitent pas par une fonction Vercel, dont le corps de requête/réponse est limité à 4,5 Mo. Références : [limites des fonctions](https://vercel.com/docs/functions/limitations), [upload direct](https://vercel.com/docs/vercel-blob/client-upload), [stockage privé](https://vercel.com/docs/vercel-blob/using-blob-sdk).

La finalisation vérifie propriétaire de la réservation, clé d'objet autorisée, taille réelle et format. Ne pas charger une URL arbitraire du client. Nettoyer les uploads abandonnés et objets orphelins ; la déduplication retire l'objet supplémentaire. Une notification répétée ne lance pas plusieurs indexations.

La suppression exclut immédiatement le document de la recherche, puis retire le fichier, les passages et les vecteurs. Un travail en cours ne doit pas pouvoir recréer un document supprimé.

### 4.2 Extraction et découpage

- PDF : extraction page par page et numérotation physique à partir de 1.
- DOCX : paragraphes dans l'ordre de lecture et texte des tableaux simples lorsque possible.
- TXT : conservation des numéros de lignes.
- Normaliser les espaces et caractères de contrôle sans supprimer les repères utiles.
- Découper prioritairement aux limites de paragraphes et de phrases.
- Paramètres initiaux proposés : **300 tokens du tokenizer d'embeddings**, avec **50 tokens de chevauchement** ; respecter la capacité réelle du modèle et ajuster par évaluation.
- Chaque passage conserve texte exact, document, ordre et repères de début et de fin.
- Versionner le parseur et la configuration de découpage pour rendre les réindexations explicables.
- À l’étape 3, une extraction complète reste `processing/extracted` ; l’interface
  affichait « Texte extrait ». Depuis l’étape 4, elle enchaîne l’indexation et
  affiche « Prêt » uniquement après publication complète de l’index.
- Limites locales d’extraction : 500 pages PDF, 50 Mio DOCX décompressés, 2 millions
  de caractères, 10 000 repères, 64 Kio UTF-8 par repère ; sous-processus borné à
  512 Mio, 20 s CPU et 30 s murales. [Détails et limites](etape-3-import-local.md).

### 4.3 Embeddings et indexation

- Calcul Sentence Transformers sur le CPU du service Python Vercel en production et localement en développement, sans API d'embeddings payante.
- Modèle retenu : `intfloat/multilingual-e5-small`, révision `614241f622f53c4eeff9890bdc4f31cfecc418b3`, CPU, 384 dimensions, préfixes `query: ` / `passage: `, normalisation L2. Lots représentatifs et documents qualifiés localement à l’étape 4 ; prototype Vercel initial conservé. La charge cloud réelle reste au jalon regroupé.
- Respecter ses conventions : préfixes éventuels, normalisation et longueur maximale.
- Utiliser `vector(384)` ; enregistrer identifiant, révision et paramètres du modèle. Borner passages, préfixes et tokens spéciaux à 512 tokens maximum avec le tokenizer E5.
- Encoder documents et questions avec le même modèle et une configuration compatible.
- Changer de modèle nécessite une réindexation complète ; ne pas mélanger les espaces vectoriels.
- Publier les passages et terminer l'indexation atomiquement avant de passer à `ready`.
- Une relance ne crée pas de doublons ; seule la génération d'indexation complète devient recherchable.

### 4.4 Recherche sémantique

- Encoder la question et rechercher par similarité cosinus dans pgvector.
- Appliquer propriétaire et sélection documentaire dans la requête avant de choisir les meilleurs résultats ; aucune recherche globale suivie d’un filtrage a posteriori.
- **Top-k = 5** par défaut, 1 à 10 demandé ; seuil **0,81** recalibré sur les vingt cas de développement pour privilégier le rappel (100 % sur ce lot ; voir [ADR 0010](decisions/0010-rappel-et-extraits-attribues.md)). Cinquante candidats avant déduplication, contexte de passages borné à 1 500 tokens ; voir [ADR 0006](decisions/0006-recherche-privee-et-seuil.md).
- Retirer les doublons et limiter la redondance due au chevauchement.
- Respecter un budget de contexte réservant de la place aux instructions, à l'historique et à la réponse.
- Commencer avec une recherche vectorielle exacte ; ajouter un index approximatif si les mesures le justifient.
- Retourner identifiants de passages, extraits, repères et scores ; un score de similarité n'est pas une probabilité de véracité.

### 4.5 Génération et citations

Le prompt demande une réponse en français fondée uniquement sur les extraits fournis, avec des références pour les affirmations factuelles. Il impose de signaler les informations manquantes et les contradictions.

- Attribuer côté serveur des références aux passages récupérés, par exemple `[S1]` et `[S2]`.
- Le LLM utilise ces références ; le serveur les résout vers les métadonnées réelles.
- Refuser les noms de fichiers, repères ou références inventés par le modèle.
- Vérifier que les références appartiennent au contexte envoyé et qu'une réponse documentaire possède au moins une citation.
- Rejeter une réponse aux références invalides avec un message explicite ; ne pas la présenter comme sourcée.
- Afficher pour chaque source : fichier, page ou repère, et extrait réellement utilisé.
- Sans passage suffisamment pertinent, retourner une abstention déterministe sans appeler le LLM.
- Si les sources répondent partiellement, répondre seulement à la partie étayée et signaler la limite.
- Traiter les instructions contenues dans les documents comme du texte documentaire, sans leur permettre de modifier les règles de l'assistant.

La validation des références assure leur traçabilité. Elle ne prouve pas que l'extrait justifie l'affirmation : la fidélité des citations doit être évaluée séparément.

### 4.6 Conversations

- Créer, lister, consulter, reprendre et supprimer uniquement les conversations du compte connecté.
- Conserver messages, ordre, état, dates et citations des réponses réussies.
- Enregistrer la sélection documentaire par échange. Limites locales gratuites : 50 conversations par compte et 100 échanges par conversation ; listes API paginées.
- Retenir au maximum les **6 derniers messages**, dans le budget de contexte. À l’étape 7, relire trois échanges avec réponse ou abstention, borner chaque texte à 500 caractères et utiliser seulement les deux dernières questions utilisateur pour contextualiser recherche/prompt ; les réponses ne constituent pas des preuves.
- Contextualiser les questions elliptiques pour la recherche ; commencer sans appel LLM supplémentaire et évaluer explicitement les questions de suivi.
- Sérialiser les générations dans une même conversation.
- Utiliser un identifiant de requête client pour éviter les doublons lors des relances réseau.
- En cas d'erreur LLM, conserver la question et l'état d'échec ; aucune réponse technique n'est enregistrée comme réponse documentaire réussie.

Après suppression d'un document, conserver les anciens messages mais retirer les extraits de leurs citations et afficher « source supprimée ». Les réponses enregistrées peuvent contenir des informations issues du document ; supprimer aussi la conversation si leur effacement est souhaité.

## 5. Architecture technique

### 5.1 Stack et responsabilités

| Composant | Responsabilité V1 |
| --- | --- |
| Next.js | Interface, parcours d'authentification et autorisation des uploads ; sur Vercel. |
| FastAPI | API authentifiée, autorisation par propriétaire, recherche et orchestration RAG ; sur Vercel. |
| LangChain | Découpage et chaîne RAG ; logique métier dans des services explicites. |
| PostgreSQL | Données métier, propriétaires, états et reprise des travaux ; service managé. |
| pgvector | Stockage et recherche des embeddings filtrés par propriétaire. |
| Sentence Transformers | Encodage des passages et questions sur le CPU du service Python. |
| API LLM | Génération depuis le contexte sélectionné, avec offre gratuite. |
| Docker | Développement reproductible ; image Python de production si nécessaire. |
| Better Auth + nom d’utilisateur/mot de passe | Authentification dans Next.js ; comptes/sessions/clés du plugin JWT dans Neon Free, JWT vérifiés par FastAPI. |
| Vercel Blob privé (retenu au cadrage) | Fichiers durables, upload direct et accès contrôlé. |
| Vercel Queues (retenu au cadrage) | Déclenchement durable des imports. |

En production, une fonction consommatrice Python remplace le worker permanent. Elle reçoit un identifiant de travail via Queues et réutilise les services d'ingestion. PostgreSQL conserve états, tentatives, verrous et points de reprise. Les événements peuvent être livrés plusieurs fois : traitements idempotents, contrôle du propriétaire et des documents supprimés obligatoires.

Prévoir une publication fiable des événements (outbox ou équivalent), une réconciliation des événements non publiés et une reprise des travaux abandonnés. Découper en lots si nécessaire pour respecter la durée d'une invocation. Les erreurs permanentes ou tentatives épuisées produisent `failed`. Aucun travail critique ne dépend d'un processus vivant après la réponse HTTP. En développement Docker, un worker peut exécuter la même logique métier.

### 5.2 Flux

```text
Navigateur → Next.js sur Vercel / Better Auth (identifiants et sessions)
            └→ Neon PostgreSQL (comptes et sessions Better Auth)
          → FastAPI sur Vercel (jeton vérifié + propriétaire)
            ├→ PostgreSQL / pgvector managé
            ├→ Sentence Transformers (question)
            └→ API LLM gratuite (contexte borné)

Navigateur → autorisation d'upload → Vercel Blob privé
Finalisation vérifiée → travail PostgreSQL → Vercel Queues
                       → fonction Python → extraction / embeddings
                       → publication atomique des passages
```

Les embeddings documentaires sont calculés à l'import. Les fichiers complets ne sont pas envoyés au LLM ; seuls question, historique retenu et extraits sélectionnés sont transmis au fournisseur externe.

### 5.3 Hébergement public sur Vercel

- Déployer Next.js et FastAPI dans un projet via **Vercel Services**. Routes `/api/v1/*` vers FastAPI ; pages et route d'autorisation d'upload vers Next.js.
- Services, runtime Container et Queues sont actuellement en **bêta** ; vérifier disponibilité, limites et coût du compte cible lors de l'intégration de chaque composant. Services/Container sont déjà vérifiés sur le prototype ; Queues sera qualifié au jalon Vercel regroupé. Références : [Services](https://vercel.com/docs/services), [runtime Container](https://vercel.com/docs/functions/runtimes/container), [Queues](https://vercel.com/docs/queues).
- Retenir Neon PostgreSQL/pgvector managé, connexion poolée ; vérifier extension, région, sauvegardes et quotas du compte lors du provisionnement.
- Documents durables dans Blob privé ; système de fichiers des fonctions uniquement temporaire.
- Conserver Sentence Transformers et E5 small dans le service Python en runtime Container : l'environnement local dépasse le bundle Python standard de 500 MB. Embarquer le modèle à la construction de l'image OCI ; tester poids compressé, mémoire, démarrage à froid et durée d'import. L'image exécute une fonction à durée bornée, pas un worker permanent.
- Région proche de la base ; mesures à chaud et à froid.
- Hébergement public HTTPS sur une URL stable `vercel.app`, sans achat de domaine. Configurer Better Auth pour cette URL ; secrets et bases distincts entre développement/Preview et Production. Limiter précisément les origines de confiance.
- Séparer Development, Preview et Production : identités/clefs d'authentification, base ou branche DB, stockage, files et secrets. Aucune donnée de production accessible aux previews.
- Configurer domaines autorisés et redirections d'authentification par environnement.
- Déployer depuis un dépôt Git connecté, exécuter tests et migrations compatibles avant publication, puis vérifier le parcours complet sur l'URL cible.
- Documenter rollback applicatif et sauvegardes DB ; un rollback applicatif ne restaure pas automatiquement les données.

**Faisabilité initiale validée :** le prototype réalise embeddings, recherche en mémoire et génération sur une Preview Vercel. Construire ensuite le socle et PostgreSQL local à l'étape 1, l'identité à l'étape 2, l'import privé à l'étape 3 et l'indexation à l'étape 4. Regrouper leurs qualifications cloud au jalon Vercel ultérieur. Si une charge réelle dépasse les limites gratuites, revoir lots, modèle ou périmètre sans souscrire de plan payant. La V1 doit fonctionner sans backend dépendant d'une machine locale.

**Budget strict de 0 €**, pour toute la stack : Vercel Hobby, Neon Free, Groq Free et Better Auth open source. Aucun achat de domaine, forfait/add-on payant, activation de facturation, moyen de paiement ajouté ou essai temporaire nécessitant un abonnement. Vérifier les inclusions du compte avant chaque provisionnement. Au dépassement, suspendre l'opération et indiquer la disponibilité ultérieure, sans montée de plan. Accepter les démarrages à froid et les suspensions compatibles avec une démonstration CV.

La grille Vercel actuelle inclut 10 GB de stockage VCR sur Hobby ; les deux images du prototype totalisent environ 1,35 GB. Viser au plus 5 GB pour ce projet et conserver une marge pour les autres usages du compte. Source : [prix et inclusions Vercel](https://vercel.com/pricing). Le compte Hobby ne peut pas acheter de dépassements ; l'offre gratuite reste une capacité bornée.

### 5.4 Arborescence cible

```text
assistant-rag/
├── README.md
├── docs/specification.md
├── frontend/                  # interface et intégration d'identité
├── backend/
│   ├── app/api/
│   ├── app/services/
│   ├── app/models/
│   ├── app/worker/             # handlers de file et exécution locale
│   ├── migrations/
│   └── tests/
├── evaluation/
│   ├── corpus/
│   ├── questions.jsonl
│   └── reports/
├── vercel.json                # services, routage et déclencheurs
├── compose.yaml
└── .env.example
```

Arborescence cible de développement ; aucun secret réel dans `.env.example`.

## 6. Modèle de données minimal

| Entité | Champs principaux | Règles |
| --- | --- | --- |
| `users` | UUID métier, identifiant fournisseur unique, dates | Création depuis identité vérifiée ; aucun mot de passe métier. |
| `documents` | UUID, `user_id`, nom, format, taille, empreinte, clé Blob, état, erreur, génération et versions, dates | Empreinte unique par utilisateur ; exclusion avant nettoyage. |
| `upload_reservations` | UUID, utilisateur, document, clé autorisée, limite, état, expiration | Jeton limité à cette réservation ; finalisation idempotente. |
| `ingestion_jobs` | UUID, `user_id`, document, état, tentatives, événement, réservation/expiration, erreur, dates | Un travail actif par document ; reprise bornée. |
| `outbox_events` | UUID, travail, type, état de publication, tentatives, dates | Reprise des événements non publiés ; consommateurs idempotents. |
| `chunks` | UUID, `user_id`, document, génération, ordre, texte, repères, tokens, embedding | Unicité document/génération/ordre ; génération publiée seulement. |
| `conversations` | UUID, `user_id`, titre, dates | Titre dérivé de la première question sans LLM. |
| `conversation_exchanges` | UUID, conversation, question, réponse, ordre, état, UUID client, sélection, dates | Unicité ordre/requête ; message utilisateur et réponse éventuelle ; échec distinct de l’abstention. |
| `conversation_sources` | Échange, propriétaire, référence, document, snapshot du passage, repères et citations | Source du même propriétaire ; textes retirés si document supprimé. |

Messages et sources héritent du propriétaire de leur conversation. Les contraintes interdisent toute relation entre une conversation, une source, un passage ou un travail et un document d'un autre propriétaire. Ne jamais dédupliquer globalement les empreintes entre comptes.

Migrations : pgvector et dimension choisie, propriétaires et contraintes. Les transactions maintiennent les invariants ; les références historiques supportent la suppression d'une source.

## 7. Contrat API cible

Routes métier sous `/api/v1`, authentifiées et filtrées par propriétaire. Listes paginées. Une sélection vide ou contenant un document indisponible produit une erreur, sans élargissement silencieux. Aucune sélection signifie tous les documents prêts du compte connecté.

| Méthode | Route | Comportement |
| --- | --- | --- |
| GET | `/health` | État public minimal sans détail interne ; contrôle DB détaillé réservé à l'exploitation. |
| POST | `/documents/uploads` | Réserver un upload privé lié au propriétaire. |
| POST | `/documents` | Finaliser l'objet autorisé après vérifications ; `202` avec UUID/état ou `200` vers un doublon du compte. |
| GET | `/documents` | Bibliothèque du compte et états. |
| GET | `/documents/{id}` | Détails, étape et erreur éventuelle. |
| GET | `/documents/{id}/extraction` | Unités canoniques privées, repères et pagination ; étape 3. |
| POST | `/documents/{id}/retry` | Relance d'un document échoué appartenant au compte. |
| DELETE | `/documents/{id}` | Exclusion immédiate et nettoyage ; `202`. |
| POST | `/search` | Question et sélection ; passages du compte, sans génération. |
| POST | `/answers` | Étape 6 locale : question, sélection et accord d’envoi ; réponse sourcée ou abstention. |
| POST | `/conversations` | Création privée ; `201`. |
| GET | `/conversations` | Liste du compte. |
| GET | `/conversations/{id}` | Titre et dates privés de la conversation. |
| GET | `/conversations/{id}/messages` | Messages et sources du propriétaire. |
| POST | `/conversations/{id}/messages` | Question, identifiant de requête et sélection ; réponse, sources et état. |
| DELETE | `/conversations/{id}` | Suppression avec messages et citations ; `204`. |

Pages `/sign-up` et `/sign-in` avec `prenom.nom`/mot de passe ; routes Better Auth limitées sous `/api/auth/*`. JWKS public ; émission JWT exclusivement côté serveur pour FastAPI. Aucune récupération automatique par e-mail. Au jalon Vercel, l’endpoint Next.js cible `/api/uploads/token` vérifiera session et réservation avant émission du jeton Blob limité. Les callbacks d'upload et de file sont authentifiés séparément ; ils restent distincts des routes utilisateur.

À l’étape 5, `POST /api/v1/search` est implémenté localement : question de
1 000 caractères, historique de quatre messages bornés à 500 caractères
(seules les deux dernières questions utilisateur sont utilisées), sélection
`null` ou liste non vide de 50 UUID maximum. La réponse distingue `matches`,
`no_match` et `empty_corpus`, avec triplet document/génération/ordre, texte exact,
repères, score, compte de tokens et versions. Une sélection vide est une 422,
un UUID étranger/inexistant une 404, un document non prêt/incompatible une 409.
Session expirée/révoquée : 401 ; file pleine : 429 ; calcul indisponible/délai : 503.
Les erreurs techniques ne sont jamais des `no_match` et aucun vecteur n’est exposé.

À l’étape 6, `/answers` ajoute `allow_external_processing`, faux par défaut :
les passages ne sont pas transmis à Groq sans accord. La réponse réussie contient
`state` (`answered` ou `insufficient_context`), texte assemblé côté serveur,
affirmations/preuves et seules sources citées. Une erreur reste HTTP avec code
stable, sans prétendre être une réponse ou une abstention. Les espaces/retours
à la ligne des citations peuvent être alignés ; le texte exact original est
rétabli, sans changer mot, casse, nombre ni ponctuation. Références, repères et
noms de fichiers sont résolus depuis les passages autorisés. Les comptes et
sources sont revalidés après génération. Aucun historique n’est créé ici.

Les échanges persistants de l’étape 7 distinguent `answered`, `insufficient_context` et `failed`. Les erreurs exposent code stable, message lisible et identifiant de requête : `401` si session absente/invalide, `403` si action interdite, `404` pour ressource inconnue ou d'un autre compte, `400` pour sélection invalide, `409` pour conflit, `413`, `415`, `422`, `429`, `502`, `504` selon la cause.

## 8. Contrainte d'API LLM gratuite

### 8.1 Choix retenu et vérification

Retenir **Groq Free**, avec **`openai/gpt-oss-120b`** et un adaptateur de fournisseur côté FastAPI. Aucun abonnement Google AI, passerelle payante ou fallback payant. Le modèle reste configurable via `LLM_MODEL` ; tout remplacement impose de vérifier accès gratuit, quotas et réponses sourcées. Sources consultées le 11 octobre 2026 : [modèles Groq](https://console.groq.com/docs/models), [offre Free et facturation](https://console.groq.com/docs/billing-faqs).

Les quotas Free publiés sont 30 requêtes/minute, 1 000/jour, 8 000 tokens/minute et 200 000/jour pour ce modèle, partagés par l'organisation. Les relever sur le compte réel avant intégration ; ne pas supposer ces valeurs permanentes. Source : [limites Groq](https://console.groq.com/docs/rate-limits).

Budget initial du pilote : entrée totale 2 500 tokens et completion 600 tokens, raisonnement inclus, effort `low` ; 10 tentatives/jour par utilisateur, 50 globalement et 2/minute, une génération simultanée. Les retries consomment aussi ces réservations. Ajuster seulement après mesure et vérification des limites du compte. Détail, calcul et coût d'infrastructure : [rapport de cadrage](etape-0-faisabilite.md).

Activer Zero Data Retention dans les contrôles Groq avant des documents personnels et vérifier les conditions du compte. Informer de la transmission des extraits et des exceptions de rétention décrites par le fournisseur. Source : [données Groq](https://console.groq.com/docs/your-data).

### 8.2 Exigences d'intégration

- Clé exclusivement côté backend, hors dépôt et bundle frontend.
- Projet restant sur l'offre gratuite ; aucune activation de facturation ou bascule automatique vers une offre payante.
- Aucun outil de recherche web ou service tarifé dans la chaîne V1.
- Limiteur distribué par compte et plafond global partagé, dans PostgreSQL ou un stockage commun ; plafond de tokens et une génération globale simultanée par défaut, protégée par un verrou à expiration. Les compteurs en mémoire ne suffisent pas entre instances Vercel.
- Au maximum deux nouvelles tentatives temporisées pour une erreur transitoire, dans le délai global ; respecter `Retry-After` s'il existe.
- Si quota épuisé, arrêter les appels et afficher une erreur permettant une relance ultérieure.
- Adaptateur remplaçable sans réécrire recherche et conversations.
- Fournisseur simulé dans les tests automatisés ; essais réels activés explicitement et bornés.

**Critère de faisabilité :** obtenir une clé, réussir une génération RAG gratuite et constater un quota suffisant pour une démonstration. Si ce critère échoue, revoir le fournisseur avant l'intégration. Une gratuité illimitée n'est pas garantie.

## 9. Exigences non fonctionnelles

### Fiabilité

Documents prêts, vecteurs et conversations survivent aux redéploiements Vercel, au remplacement des instances et aux redémarrages Docker en développement. Une interruption de traitement ne rend aucun index partiel recherchable. Relances et suppressions sont idempotentes. Les erreurs d'un fichier ou du fournisseur LLM ne bloquent pas les autres parcours.

### Capacité et performance

Cible du pilote : **50 documents, 100 Mio d'originaux et 10 000 passages par utilisateur** ; plafonds globaux **100 documents, 600 Mio et 20 000 passages**, un import simultané. En production, le stockage des originaux est limité à 400 Mio (100 Mio en Preview). Arrêter l’indexation à 400 Mio de base réellement occupée : le plan Neon Marketplace provisionné annonce 0,5 Go. Les réservations d’upload contrôlent également la taille de la base avec leur plafond d’environnement. Toutes les limites s'appliquent simultanément et restent à confirmer sur le compte. Sur une configuration Vercel de référence documentée, modèle chargé, viser une recherche p95 inférieure à **2 secondes** et une réponse complète p95 inférieure à **20 secondes**, hors attente de quota. Mesurer au moins 30 requêtes et publier les conditions ; ces valeurs sont des objectifs, pas des performances acquises.

Mesurer l'import séparément. Publier aussi les latences à froid, le chargement du modèle et les conditions de concurrence ; ne pas mélanger ces mesures avec les objectifs à chaud. La phase fournisseur locale est bornée à 55 secondes avec un timeout réseau de
15 secondes ; la recherche E5 préalable peut durer jusqu’à 105 secondes à froid.
Le proxy/client attend au maximum 175/180 secondes. Un bail de 70 secondes
protège la phase fournisseur et les compteurs distribués ; les performances
Vercel et l’objectif de réponse à chaud restent à qualifier.

### Protection des données et robustesse

- Production publique HTTPS avec authentification obligatoire et autorisation par propriétaire sur toutes les données métier.
- PostgreSQL via connexions chiffrées et identifiants serveur uniquement, CORS limité aux origines autorisées, secrets isolés par environnement et fichiers Blob privés.
- Limites sur fichiers, extraction, questions, contexte et réponses.
- Journaux d'identifiants, durées, états et erreurs, sans texte documentaire ni secret par défaut.
- Informer l'utilisateur que les extraits sélectionnés sont transmis au fournisseur LLM.
- Affichage Markdown sans HTML arbitraire ; sources traitées comme contenu non fiable.

### Exploitabilité

Prévoir `.env.example`, migrations, vérifications de santé, volumes persistants locaux et lancement Docker Compose documenté. Ajouter un guide Vercel : routage, identité, stockage, files, régions, migrations, previews, production et rollback. Paramètres : DB poolée, Blob, fournisseur d'identité et émetteur, domaines autorisés, région/file, LLM et clé, embeddings, découpage, recherche, quotas et délais. Seules les clés explicitement publiables d'identité peuvent être exposées au frontend.

## 10. Tests et évaluation

### 10.1 Corpus et annotations

Préparer un corpus stable et autorisé avec les trois formats, plusieurs sujets, des formulations proches, une contradiction et des fichiers invalides. Constituer **30 questions minimum** : 15 factuelles, 5 nécessitant plusieurs passages ou documents, 5 hors corpus et 5 suivis de conversation.

Chaque cas possède un identifiant, la sélection documentaire, la réponse attendue ou l'abstention, les sources pertinentes et les éléments à vérifier. Les suivis incluent l'historique nécessaire. Le [corpus Iris initial](../evaluation/README.md) est présent : quatre documents exploitables, trois négatifs, 22 passages annotés et 30 cas dans `evaluation/questions.jsonl`. Les passages canoniques sont reliés aux chunks réels par texte et repères dans
la qualification de recherche de l’étape 5, sur une base locale isolée.

Réserver au moins 10 cas pour la validation finale sans les utiliser pour régler les paramètres. Les rapports distinguent réglage et validation.

### 10.2 Métriques et objectifs initiaux proposés

| Indicateur | Définition | Objectif V1 |
| --- | --- | --- |
| Recall@5 | Part des passages pertinents annotés retrouvés dans les cinq premiers, moyennée sur les questions répondables. | ≥ 80 % |
| Exactitude | Part des réponses répondables satisfaisant une grille humaine des éléments attendus. | ≥ 80 % |
| Validité des références | Citations résolues vers des passages réellement envoyés au LLM. | 100 % |
| Fidélité des citations | Affirmations citées réellement justifiées par leur extrait selon revue humaine. | ≥ 90 % |
| Couverture des citations | Affirmations factuelles vérifiables accompagnées d'une source justificative. | ≥ 90 % |
| Abstention hors corpus | Questions hors corpus sans réponse factuelle inventée. | ≥ 80 % |

Publier nombres bruts et pourcentages, notamment sur le petit lot final. Ces seuils sont des objectifs à réviser explicitement si le corpus évolue ; aucun évaluateur LLM payant n'est requis.

Les rapports enregistrent corpus, modèles et révisions, découpage, recherche, prompt, date, latences et erreurs. Les erreurs de quota sont des erreurs techniques et ne sont pas comptées comme des abstentions réussies.

### 10.3 Vérifications techniques

- Unitaires : validation, parsing, repères, découpage, citations et budget de contexte.
- Intégration PostgreSQL/pgvector : import, recherche filtrée, relance, suppression et persistance.
- Fournisseur simulé : succès, citation inventée, délai dépassé, quota et erreur réseau.
- Bout en bout en local, puis en preview et production aux jalons de déploiement : inscription/connexion → session → importer → attendre `ready` → questionner → ouvrir une source → recharger → déconnecter ; origines autorisées, mauvais identifiants, révocation et expiration couverts.
- Reprise : interruption de fonction, événement dupliqué, publication échouée, upload abandonné, récupération sans doublons et suppression pendant l'indexation.
- Cas négatifs : corpus vide, sélection indisponible, PDF scanné, fichier trop volumineux et instructions malveillantes dans un document.
- Isolation avec deux comptes : listes, UUID directs, recherche, citations, relances, suppressions et objets privés inaccessibles à l'autre compte.
- Identité : jeton manquant, expiré ou falsifié, origine invalide, déconnexion et expiration.
- Hébergement : upload de 20 Mio, démarrage à froid, mémoire/durée, persistance après redéploiement et séparation Preview/Production.
- Budget : quotas atteints et retries simulés arrêtent les opérations ; aucun chemin ne souscrit un plan ou appelle un fournisseur payant. Relever les plans gratuits et les usages avant publication.

## 11. Étapes de développement de la V1

Étapes ordonnées par dépendance. Le socle prépare l'identité et l'architecture Vercel ; le corpus est préparé tôt, puis enrichi. Sur demande du porteur du 11 octobre 2026, les développements et tests courants restent locaux. Aucun déploiement à chaque implémentation : la qualification cloud et le provisionnement des services managés seront regroupés à un jalon ultérieur, lorsque le projet aura suffisamment avancé. Les essais locaux ne valent pas certification cloud ; l'authentification et la publication Vercel restent obligatoires pour livrer la V1.

### Étape 0 — Cadrage et faisabilité Vercel

**Travaux :** arrêter l'architecture cible ; tester le LLM gratuit et les embeddings ; vérifier le plan Vercel, Services et le runtime Python/Container par un prototype ; documenter limites et budget prévisionnel ; préparer corpus et annotations.

**Livrables :** décisions, architecture cible, limites, budget et corpus initial.

**Validation :** API gratuite accessible sur un compte Free confirmé, modèle/dépendances exécutables sur Vercel, quotas observés, limites et budget prévisionnel documentés. Le provisionnement et les essais des autres services interviennent quand leur intégration devient nécessaire.

**État au 11 octobre 2026 : validée sur le périmètre approuvé par le porteur.** [Décisions](decisions/0001-groq-et-architecture-v1.md), [budget et preuves](etape-0-faisabilite.md), corpus et scripts d'essai sont présents. Le compte Groq Free a été confirmé et les appels réels ont réussi. Le projet Vercel Hobby `assistant-rag` exécute FastAPI Container, E5 CPU et une génération sourcée sur une fixture synthétique en Preview `fra1`. Le porteur demande de traiter les autres contrôles au moment du besoin ; leur répartition est consignée dans le rapport.

- [x] Architecture, limites et budget prévisionnel documentés.
- [x] Corpus initial et annotations disponibles.
- [x] Appel Groq Free réel réussi, usage et quotas consignés.
- [x] FastAPI et E5 embarqué exécutés sur Vercel ; recherche et citation vérifiées.
- [x] Poids de l'image, mémoire et invocations avec/sans modèle chargé mesurés.

Les contrôles reportés restent des critères des étapes concernées, avec authentification et hébergement public obligatoires pour la V1.

### Étape 1 — Socle local

**Dépendance :** étape 0.

**Travaux :** Next.js, FastAPI, Docker Compose, migrations Alembic, PostgreSQL/pgvector local, variables privées, services et routage de même origine. Préparer les frontières d'intégration sans provisionner de base managée ni déployer.

**Livrables :** environnement local reproductible, page initiale, API minimale, base persistante, dépendances verrouillées et commandes de vérification documentées.

**Validation :** parcours navigateur → Next.js → FastAPI → PostgreSQL réussi localement ; pgvector actif ; migrations testées sur une base isolée et réapplicables ; données vectorielles persistantes après recréation du conteneur PostgreSQL ; tests, lint, types et build réussis. Les preuves E5/Groq du prototype sont conservées. Neon, HTTPS et persistance après redéploiement seront qualifiés au prochain jalon Vercel.

**État au 11 octobre 2026 : validée en local.** [Résultats et limites déclarées](etape-1-socle-local.md), [guide de lancement](developpement-local.md). 13 tests réussis, lint/types/build réussis, persistance vérifiée après recréation du conteneur PostgreSQL. Aucun déploiement ni service cloud créé.

- [x] Next.js et FastAPI démarrent avec Docker Compose et communiquent sur la même origine.
- [x] PostgreSQL/pgvector, migrations versionnées et volume persistant opérationnels.
- [x] Cas d'indisponibilité et erreurs sans secrets couverts.
- [x] Parcours navigateur bureau/mobile, types, lint et build vérifiés.
- [x] Configuration et vérifications reproductibles documentées ; étape 0 conservée.

### Étape 2 — Authentification et isolation

**Dépendance :** étape 1.

**Travaux :** intégrer Better Auth et ses migrations dans PostgreSQL local, compatible Neon Free ; implémenter inscription/connexion `prenom.nom` et mot de passe, sessions, déconnexion, JWT/JWKS, validation FastAPI, propriétaires et contraintes, routes protégées et origines locales. Les domaines publics et Neon seront configurés au jalon Vercel. Aucun domaine acheté ni service d'e-mails.

**Livrables :** parcours d'identité et contrôle d'accès réutilisable.

**Validation :** deux comptes isolés, API anonyme et jetons invalides refusés, expiration gérée. Toutes les futures routes réutilisent ces contrôles et tests.

**Statut : validée en local le 11 octobre 2026.** [Rapport et limites](etape-2-identite-locale.md).

- [x] Inscription et connexion `prenom.nom` / mot de passe, sessions et déconnexion.
- [x] JWT/JWKS vérifiés dans FastAPI, session active et révocation immédiate.
- [x] Deux comptes isolés, UUID stable, FK et 404 indistinguables.
- [x] 38 tests locaux : bootstrap, API/JWT, PostgreSQL et Chromium bureau/mobile.
- [x] Lint, types, build, secrets hors bundle public et persistance vérifiés.
- [x] Aucun déploiement ni provisionnement cloud ; qualification HTTPS/Neon différée.


### Étape 3 — Import privé et extraction

**Dépendance :** étape 2.

**Travaux :** upload autorisé, finalisation, empreintes par compte, publication fiable, consommateur Python, parseurs/repères, états, erreurs, relance, suppression et nettoyage. Valider stockage et traitements avec des adaptateurs locaux ; intégrer et qualifier Blob privé, upload direct et Queues au jalon Vercel.

**Livrables :** bibliothèque privée avec extraction vérifiable localement, puis qualification Vercel au jalon regroupé.

**Statut : validée en local le 11 octobre 2026.** [Parcours, preuves et limites](etape-3-import-local.md) · [ADR 0004](decisions/0004-import-local-durable.md).

- [x] Réservation authentifiée, capacité courte, envoi direct privé et finalisation vérifiée.
- [x] PDF/DOCX/TXT localisables ; fichier exact de 20 Mio sur bureau et mobile.
- [x] Invalides, scan, chiffrement, encodage et limites d’extraction traités explicitement.
- [x] Deux comptes isolés ; empreinte dédupliquée uniquement par propriétaire.
- [x] Travaux durables, événement répété, upload abandonné, relance et bail interrompu.
- [x] Suppression concurrente et nettoyage ; quotas sérialisés dans PostgreSQL.
- [x] 59 tests, lint/types/build et conservation de dix originaux/textes après recréation.
- [x] Aucun appel LLM, déploiement ni provisionnement cloud ; Blob/Queues différés.

**Suite :** étape 4, découpage et indexation. Les documents extraits ne deviennent `ready` qu’après publication complète de leur index.

### Étape 4 — Découpage et indexation

**Dépendance :** étape 3.

**Travaux :** passages avec propriétaire, embeddings par lots, points de reprise, publication atomique et versions.

**Livrables :** corpus indexé et paramètres documentés.

**Validation :** vecteurs compatibles, repères fidèles, aucune duplication ; mémoire et durée mesurées localement, puis charge représentative et démarrage à froid qualifiés au jalon Vercel regroupé.

**Statut : validée en local le 11 octobre 2026.** [Preuves et limites](etape-4-indexation-locale.md) · [ADR 0005](decisions/0005-indexation-locale-reprenable.md).

- [x] Passages exacts, repères physiques et configuration versionnée, 300/50 tokens E5.
- [x] Embeddings CPU hors ligne, 384 dimensions, préfixes et norme L2 vérifiés.
- [x] Lots de 16, checkpoints, relance sans doublon et publication atomique `ready`.
- [x] Baux remplacés et suppression concurrente empêchent une publication tardive.
- [x] Isolation SQL par propriétaire et quotas partagés 10 000/20 000 passages.
- [x] Migration additive, reprise d’anciens documents et rollback sur base isolée.
- [x] 77 tests, lint/types/build ; dix originaux/textes/index conservés après remplacement.
- [x] CPU mesuré : démarrage/premier lot 49,336 s, lot chaud 5,272 s, pic RSS 963,4 Mio.
- [x] Aucun appel LLM ni déploiement ; charge et démarrage Vercel différés.

**Suite :** étape 5, recherche privée et mesure de Recall@5.

### Étape 5 — Recherche privée

**Dépendance :** étape 4.

**Travaux :** similarité, filtre propriétaire puis sélection, top-k, déduplication, seuil et Recall@5.

**Livrables :** recherche inspectable et rapport de récupération.

**Validation :** pertinence mesurée, aucune fuite entre comptes/hors sélection, corpus vide géré et paramètres enregistrés.

**Statut : validée en local le 11 octobre 2026.** [Preuves et limites](etape-5-recherche-locale.md) · [ADR 0006](decisions/0006-recherche-privee-et-seuil.md).

- [x] Recherche cosinus exacte, propriétaire et sélection filtrés avant classement.
- [x] Même E5 CPU, préfixe question, L2 et refus d’un encodage dépassant 512 tokens.
- [x] Top-k 5, seuil 0,84, déduplication et budget de passages de 1 500 tokens.
- [x] Questions/historique bornés, session vérifiée pendant l’attente et file partagée.
- [x] Corpus vide, absence de correspondance, erreur technique et sélection indisponible distincts.
- [x] Sources exactes consultables sur bureau/mobile, sans cache public ni stockage navigateur.
- [x] Recall@5 de développement 82,4 % sur 17 questions répondables ; 17 / 20 annotations couvertes.
- [x] 100 tests, lint/types/build, rollback isolé ; dix-huit index/recherches inchangés après remplacement.
- [x] Aucun appel LLM ni déploiement ; dix cas finaux réservés et charge cloud différée.

**Limite mesurée :** seulement 1 / 3 questions hors corpus sans correspondance.
Le seuil ne valide pas la présence d’une réponse ; l’abstention de génération
reste à évaluer à l’étape 6.

**Suite :** étape 6, réponses sourcées et quotas.

### Étape 6 — Réponses sourcées et quotas

**Dépendance :** étape 5.

**Travaux :** adaptateur, LangChain, prompt, budget, citations, abstention, limites par compte/globales et erreurs.

**Livrables :** réponses avec sources privées et fournisseur simulé.

**Validation :** démonstration gratuite, références inventées rejetées, quotas partagés entre instances, fidélité évaluée.

**Statut : validée techniquement en local le 12 octobre 2026, avec limites de qualité déclarées.** [Résultats](etape-6-reponses-locales.md) · [ADR 0007](decisions/0007-generation-sources-et-quotas.md).

- [x] Adaptateur Groq Free, LangChain Core, réponse JSON structurée et envoi explicitement accepté.
- [x] Tokenizer GPT-OSS hors ligne ; entrée 2 500 et completion 600 tokens, raisonnement inclus.
- [x] Références serveur, citations rétablies exactement et rejet d’une sortie invalide/tronquée.
- [x] Aucun appel sans passage ; abstention et erreurs distinctes.
- [x] 10/jour/compte, 50 globalement, 2/minute et réservation de 3 100 tokens par tentative.
- [x] Verrou global, retries comptés, `Retry-After` et suspension partagée sur 429.
- [x] Révocation ou suppression de source pendant l’appel interdit la publication.
- [x] 130 tests, lint/types/build ; 26 index/recherches et compteurs conservés après remplacement.
- [x] Deux réponses Groq étayées et une abstention sur trois cas de développement ; dix cas finaux réservés.
- [x] Aucun déploiement/provisionnement cloud ; compte Free confirmé et plafond réel documenté.

**Limite :** les trois affirmations sont étayées, mais seulement 1 / 2 réponses
répondables est entièrement complète selon les annotations. L’exemple comparatif
omet d’expliciter le remplacement daté de la politique. La qualité V1 n’est pas
certifiée par ce petit échantillon ; la validation finale reste à l’étape 8.

**Suite :** étape 7, interface de conversations et historique persistant.

### Étape 7 — Interface et conversations

**Dépendance :** étape 6 ; interface documentaire possible dès l'étape 3.

**Travaux :** bibliothèque, sélection, chat, sources, historique/suivis, suppressions, expiration et prévention des doubles envois.

**Livrables :** parcours authentifié complet en local, puis qualifié sur Preview au jalon Vercel regroupé.

**Validation :** importer, questionner, consulter, reprendre et déconnecter ; sources/historique privés ; suivis évalués.

**Statut : validée en local le 12 octobre 2026.**
[Parcours et preuves](etape-7-conversations-locales.md) · [ADR 0008](decisions/0008-conversations-privees-et-reprise.md).

- [x] Conversations, échanges, sélection, dates et citations privés et persistants.
- [x] Historique serveur borné, recherche renouvelée et suivi Q28 vérifié avec E5 réel/fournisseur simulé.
- [x] Rechargement, reconnexion, session révoquée et interface bureau/mobile.
- [x] Sérialisation, UUID stable et reprise réseau sans double génération.
- [x] Questions échouées conservées ; source supprimée sans extrait ; suppression de conversation sans remise à zéro des quotas.
- [x] 156 tests, lint/types/build ; 16 conversations, 20 échanges et 10 sources inchangés après remplacement.
- [x] Aucun appel Groq réel ni déploiement ; dix cas finaux réservés.

**Suite :** étape 8, qualification finale et publication au jalon Vercel regroupé.

### Étape 8 — Qualification et publication

**Dépendance :** étape 7.

**Travaux :** tests techniques/intercomptes, lot final réservé, performances, séparation des environnements, identité et URL stable `vercel.app` de production, exports de sauvegarde sans option payante, migrations, vérification du budget de 0 €, publication HTTPS et parcours après déploiement.

**Livrables :** URL Vercel publique, rapport, guides local/Vercel, limites, coûts et rollback.

**Validation :** parcours complet avec deux comptes sur production sans machine locale, persistance après redéploiement et critères ci-dessous. Corriger ou faire accepter tout écart avant de déclarer la V1 conforme.

**État au 13 octobre 2026 :** étape achevée. Publication, qualité du lot réservé, parcours navigateur, performances, sauvegarde et persistance vérifiés. La non-régression v7 atteint les seuils avec 7/8 réponses complètes et aucune erreur technique. [Rapport détaillé](etape-8-publication.md) et [revue humaine](revue-qualite-etape-8.md). Le premier lot final en échec reste conservé ; aucun réglage n’a utilisé le nouveau lot réservé. Sa répétition v7 est explicitement une non-régression sur des cas déjà ouverts, analysée par l’agent ; la validation humaine concerne le lot indépendant v5.

## 12. Critères de livraison

- [x] Les sept fonctionnalités du README et F08/F09 sont démontrables.
- [x] Inscription `prenom.nom`/mot de passe, connexion, déconnexion et expiration fonctionnent ; absence de récupération automatique documentée.
- [x] Deux comptes ne peuvent accéder aux données privées de l'autre.
- [x] La production HTTPS Vercel réalise le parcours complet sans machine locale active.
- [x] Les fichiers privés de 20 Mio sont importés sans dépasser le payload des fonctions.
- [x] Preview et Production ont données et secrets isolés.
- [x] PDF textuel, DOCX et TXT passent le parcours complet.
- [x] Les fichiers invalides ou trop volumineux sont traités proprement.
- [x] Les citations sont valides et les extraits vérifiables.
- [x] Le manque d'information déclenche une abstention explicite.
- [x] La sélection documentaire est respectée à chaque question.
- [x] Documents, vecteurs et conversations persistent après redémarrage et redéploiement Vercel.
- [x] Reprise, relance et suppression maintiennent des données cohérentes.
- [x] L'API fonctionne sur l'offre gratuite et les quotas sont gérés.
- [x] Les tests passent et les objectifs d'évaluation sont atteints sur le lot réservé.
- [x] Performances, limites et conditions de reproduction sont publiées.
- [x] Installation locale, Vercel, migrations, sauvegardes, coûts et rollback sont documentés sans secret dans le dépôt.
- [x] Développement et démonstration restent à 0 € : plans gratuits vérifiés, URL `vercel.app`, aucune dépense/add-on et opérations suspendues au quota.

## 13. Exigences confirmées et validations par étape

| Décision | Proposition V1 | Validation |
| --- | --- | --- |
| Utilisation | Vercel public, comptes authentifiés, bibliothèque privée par compte | Exigence confirmée |
| Fournisseur et modèle LLM | Groq Free, `openai/gpt-oss-120b` | Appels réels réussis localement et depuis Vercel ; Free confirmé dans Billing ; en-têtes 1 000 requêtes/jour et 8 000 tokens/minute |
| Embeddings | E5 small, révision figée dans ADR 0001, CPU, 384 dimensions | Lots 300 tokens qualifiés à l’étape 4 ; Recall@5 de développement 82,4 % à l’étape 5 ; charge cloud mesurée à l’étape 8 |
| Limites | 50 documents/100 Mio/10 000 passages par compte ; 20 Mio par fichier ; plafonds globaux du rapport | Limites et quotas partagés qualifiés ; Production 400 Mio, Preview 100 Mio, Neon Free 0,5 Go |
| Découpage et recherche | 300/50 tokens, top-k 5, seuil 0,81, contexte 1 500 tokens | Recall@5 100 % sur développement et nouveau lot réservé ; premier lot en échec conservé |
| Authentification et Vercel public | Obligatoires dès V1 | Exigence confirmée |
| Fournisseur d'identité | Better Auth open source + `prenom.nom`/mot de passe ; PostgreSQL local et Neon Free | Inscription, connexion, révocation, expiration et isolation qualifiées en production |
| Infrastructure | Services, Container, Queues, Blob privé, Neon PostgreSQL/pgvector | Services/Container/Queues, Neon Free et Blob privé qualifiés sur Hobby ; limites et coûts documentés |
| Budget et finalité | 0 €, projet CV personnel non commercial, offres gratuites uniquement | Exigence confirmée ; contrôles au provisionnement et à la publication |

## 14. Évolutions après V1

Partage entre comptes, organisations et rôles avancés, plusieurs bibliothèques par compte, OCR, tableaux enrichis, recherche hybride et reranking, streaming et connecteurs. Prioriser ces évolutions à partir des limites mesurées dans le rapport V1.
