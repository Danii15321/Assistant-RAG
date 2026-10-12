# ADR 0007 — Génération privée, preuves textuelles et quotas

- Date : 12 octobre 2026.
- Statut : acceptée et qualifiée techniquement en local ; limites de complétude documentées.
- Références : [spécification](../specification.md), [recherche](0006-recherche-privee-et-seuil.md).

## Décision

Ajouter `POST /api/v1/answers`, sans enregistrer de conversation à cette étape.
Réutiliser la recherche privée, son historique borné et E5 local. Aucun passage
pertinent : abstention déterministe, sans Groq ni réservation de quota. Avant
l’envoi de passages, demander l’accord explicite dans l’interface. Les réponses
et extraits restent en mémoire dans le navigateur ; aucune persistance locale.

Conserver Groq Free et `openai/gpt-oss-120b`, sans outil, service tier payant,
passerelle ou autre fournisseur automatique. La génération reste désactivée sans
clé serveur et confirmation du niveau Free. Le porteur a confirmé ce niveau le
11 octobre. Le montage local ne contient que la clé Groq : aucun secret Vercel
ou d’identité n’est transmis au frontend, au worker, à la migration ou aux tests.

Utiliser LangChain Core pour construire le prompt, avec le métier explicite dans
les services. Désactiver le traçage LangSmith ; aucun évaluateur LLM supplémentaire.
Demander une réponse JSON structurée : état, affirmations et preuves (identifiant
serveur + citation textuelle). Les noms de fichiers et repères proviennent des
passages privés, pas du modèle. Refuser références absentes, citations non
contenues mot pour mot dans le contexte, réponses tronquées, objets mal formés
et nombres écrits en chiffres absents des preuves. Les seuls espaces/retours à la ligne peuvent
être alignés ; l’extrait est ensuite rétabli exactement depuis le fichier, sans
modifier mot, casse, nombre ou ponctuation. Ce contrôle numérique est conservateur ; il ne
remplace pas une évaluation humaine de la fidélité sémantique.

Le tokenizer GPT-OSS `o200k_harmony` est figé par tiktoken 0.12.0. Son vocabulaire
public vérifié par empreinte est téléchargé à la construction de l’image et
réutilisé hors ligne. Compter question/historique utilisateur, instructions,
passages et schéma JSON, avec une marge de 256 tokens pour le format fournisseur.
Budget d’entrée 2 500 tokens, completion 600 (raisonnement inclus), effort `low`.
Retenir des passages entiers dans ce budget ; une impossibilité est une erreur
explicite, pas une abstention prétendument réussie.

Réserver les tentatives dans PostgreSQL sous verrou du singleton : 10 par compte
et jour UTC, 50 globalement, 2 par minute et 155 000 tokens réservés/jour globalement.
Une tentative réserve 3 100 tokens (plafonds entrée + completion) ; les erreurs et retries ne
remboursent pas cette réservation. Une seule génération globale, avec bail de
70 secondes et jeton empêchant un ancien appel de libérer un bail remplacé.
La suppression d’une session n’efface pas le verrou pendant un appel en cours.

Un 429 Groq suspend les appels et conserve un délai partagé, sans retry immédiat.
Les seules erreurs transitoires peuvent être retentées au plus deux fois, dans
la limite de temps et des compteurs ; `Retry-After` est respecté. Le plafond de
2/minute peut interrompre ces retries avant leur maximum. Revalider session et
sources avant chaque envoi puis avant publication ; après suppression ou
réindexation, rejeter la réponse sans exposer ses extraits.

## Conséquences et limites

La migration additive `0006_generation` ne stocke que les compteurs, états,
tokens et baux : aucun prompt, texte documentaire ou réponse. Rétention des
compteurs : sept jours, purge au prochain appel ; les tentatives interrompues
restent comptabilisées. Une suppression de compte efface ses compteurs.

Les tests utilisent un fournisseur HTTP synthétique isolé, sans clé réelle.
La qualification réelle est explicitement activée et bornée sur les seules
fixtures publiques de développement. Une première exécution a été refusée par
la validation locale ; cette observation reste conservée séparément.
Les dix cas finaux ne sont pas utilisés pour régler le prompt.

Les preuves textuelles attestent la provenance, pas automatiquement que chaque
phrase est justifiée. La fidélité, les contradictions et les abstentions doivent
encore être évaluées sur le lot final à l’étape 8. Les conversations/historiques
persistants arrivent à l’étape 7. La qualification Vercel reste différée.

Sources : [sorties structurées Groq](https://console.groq.com/docs/structured-outputs),
[tokenizer GPT-OSS](https://github.com/openai/gpt-oss/blob/main/gpt_oss/tokenizer.py),
[encodage et empreinte tiktoken](https://github.com/openai/tiktoken/blob/main/tiktoken_ext/openai_public.py).
