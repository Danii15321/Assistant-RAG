# Étape 6 — Réponses sourcées et quotas locaux

**Étape 6 validée techniquement en local le 12 octobre 2026.** La qualification
de qualité reste limitée au petit lot de développement décrit ci-dessous. Budget strict **0 €**, aucun déploiement Vercel ni
provisionnement cloud. [Décision et limites](decisions/0007-generation-sources-et-quotas.md).

## Parcours

Dans [la recherche locale](http://localhost:3000/search), saisir une question,
choisir ses documents, puis accepter l’envoi à Groq et cliquer « Générer une
réponse sourcée ». Les affirmations renvoient à `[S1]`, etc. « Vérifier la source »
affiche la citation textuelle, le nom du fichier, le repère et le passage exact.
L’interface échappe le texte et n’interprète aucun HTML fourni par les documents
ou le LLM. La recherche des passages seule reste entièrement locale.

L’absence de passage pertinent n’appelle pas Groq. Si les passages trouvés ne
contiennent pas la réponse, le modèle doit s’abstenir. Une erreur réseau, quota,
source supprimée ou citation invalide s’affiche comme erreur ; aucune fausse
réponse documentaire n’est publiée. Les conversations ne sont pas encore
conservées ; elles sont le périmètre de l’étape 7.

Pour des documents personnels, activer Zero Data Retention dans les réglages
Groq avant leur envoi. La qualification de cette étape utilise uniquement les
fixtures fictives publiques. Les contrôles de rétention du compte ne sont pas
certifiés par une clé API ni par le code.

## Contrat et paramètres

`POST /api/v1/answers` reprend le contrat de recherche (`question`, sélection,
top-k et historique bornés) et ajoute `allow_external_processing`, faux par
défaut. L’accord est requis avant tout envoi externe. Le serveur déduit le
propriétaire de la session, jamais du corps client.

La réponse distingue `answered` et `insufficient_context`, avec texte assemblé
par le serveur, affirmations/preuves, seules sources citées, version du prompt,
durée et indication d’appel fournisseur. Les métadonnées et vecteurs du modèle
ne sont pas acceptés comme sources. Réponses privées, `Cache-Control: no-store`.

| Contrôle | Valeur |
| --- | --- |
| Fournisseur / modèle | Groq Free / `openai/gpt-oss-120b` |
| Prompt / sortie | LangChain Core, JSON strict, 1 à 4 affirmations sourcées |
| Entrée | 2 500 tokens, o200k_harmony + marge de format 256 |
| Completion | 600 tokens, raisonnement inclus ; effort `low` |
| Quotas | 10/jour/compte, 50/jour globalement, 2/minute ; jour UTC |
| Tokens réservés | 3 100 par tentative ; maximum global 155 000/jour |
| Concurrence | Un bail PostgreSQL global, jeton remplacé protégé |
| Fournisseur | Fenêtre de 55 s, timeout réseau 15 s, corps maximum 32 Kio |
| Proxy / client | 175 / 180 s, avec recherche préalable jusqu’à 105 s |
| Rétention | Compteurs pendant sept jours ; pas de texte ni réponse |

Une lecture réseau bloquante peut dépasser la fenêtre fournisseur d’au plus
son timeout courant ; le bail garde une marge. Chaque retry réserve une nouvelle
tentative. Aucun quota n’active une facturation, un autre modèle ou un fournisseur
payant. Les baux expirés ne permettent pas une publication tardive.

## Résultats réellement obtenus

**130 tests passent** : quatre scripts de configuration, 61 backend,
29 PostgreSQL et 36 Chromium sur bureau/mobile. Ruff/format, mypy, ESLint,
TypeScript et build de production passent. Les tests vérifient les citations
inventées, la normalisation des seuls espaces de mise en page, les quotas atomiques,
les délais/réseau, la révocation pendant l’appel et la suppression d’une source.
[Rapport technique](../evaluation/reports/answers-step6-local.json).

Les [captures bureau](../evaluation/reports/step6-desktop.png) et
[mobile](../evaluation/reports/step6-mobile.png) ont été inspectées : réponse,
liens de citation, accord d’envoi et extraits consultables, sans débordement.
La revue React contrôle l’authentification serveur, les effets nettoyés,
l’annulation, les états privés, les libellés et l’affichage du texte échappé.

Après recréation de PostgreSQL puis remplacement API/worker, **26 documents**
de test conservent originaux, textes, vecteurs et résultats de recherche ; le
compteur de génération restant après les scénarios est également inchangé.
[Preuve de persistance](../evaluation/reports/answers-step6-persistence.json).
Les rapports des étapes précédentes restent conservés.

[Essais Groq](../evaluation/reports/answers-step6-groq.json) et
[revue de fidélité](../evaluation/reports/answers-step6-fidelity.json) :

| Mesure sur trois cas de développement | Résultat |
| --- | --- |
| Réponses / abstention | Deux réponses étayées ; une abstention correcte |
| Références et affirmations justifiées | 3 / 3, vérifiées depuis le texte canonique |
| Affirmations factuelles citées | 3 / 3 |
| Réponses entièrement complètes selon les annotations | **1 / 2** |
| Éléments attendus couverts | 3 / 4 |
| Hors corpus sans réponse inventée | 1 / 1 |
| Cas finaux exécutés | **0 / 10** |

Q16 cite correctement les 45 jours de 2026 et les 30 jours de l’archive 2025,
mais n’explicite pas le remplacement au 1er septembre 2026. La complétude reste
insuffisante sur cet exemple ; ces résultats ne certifient pas les objectifs V1.
L’instruction malveillante de l’archive n’a pas été suivie dans cet essai.
La provenance textuelle validée ne garantit pas toute la fidélité sémantique.

Le journal instrumenté contient **trois appels Groq réels** : la réponse Q02
reçue avec des espaces lissés a été revalidée sans nouvel appel, puis Q16/Q21
ont utilisé deux nouvelles requêtes. Une première exécution antérieure a été
refusée par la validation et n’avait pas conservé le nombre exact de requêtes :
[observation initiale](../evaluation/reports/answers-step6-initial.json).
On rapporte donc un maximum total de **six appels** pour l’étape, pas un nombre
exact inventé. Toutes ces requêtes portent sur les fixtures publiques, avec le
compte Free confirmé ; aucun appel réel n’appartient à la suite automatisée.

## Vérification et reproduction

```bash
# Copie seulement la clé Groq existante, jamais les secrets Vercel.
python3 scripts/local/configure_llm.py --free-confirmed
docker compose up -d --no-deps --force-recreate backend

# Fournisseur simulé : aucun appel Groq réel.
bash scripts/local/check.sh

# Opt-in : au plus trois appels instrumentés ; réutilise les réponses déjà reçues.
python3 scripts/local/qualify_answers.py --real --revalidate-retained
```

Le niveau Free doit avoir été confirmé dans le compte avant `--free-confirmed`.
La clé dans `.env.local` reste intacte ; `.secrets/groq_api_key` est privé (`0600`,
dossier `0700`) et exclu des sources publiées. Les images embarquent le vocabulaire
public du tokenizer ; l’exécution ordinaire et les tests n’ont pas à le télécharger.
Le faux fournisseur est accessible uniquement dans le profil Docker de test,
sans port publié et sans accès à la clé réelle.

L’essai réel utilise `assistant_rag_evaluation`, réimporte les documents par le
pipeline E5 réel et traite uniquement Q02, Q16, Q21 du lot de développement.
Une interruption ne doit pas être confondue avec une abstention.
Le journal privé de l’évaluation conserve les seules réponses publiques reçues
et plafonne trois nouvelles requêtes pour ce lot. `--revalidate-retained` permet
de revalider ces réponses sans les redemander au fournisseur ; les appels et
réutilisations sont distingués dans le rapport. Les dix cas
finaux restent réservés ; aucun chiffre de validation finale n’est annoncé.

## Migration et suite

La migration additive `0006_generation` ajoute seulement les réservations et
limites. Une sauvegarde locale privée précède l’application ; comptes, fichiers,
textes et vecteurs sont conservés. Le rollback supprime les compteurs et la file
de limites et exige le code de l’étape 5. Il est testé seulement sur base isolée.
Ne pas l’utiliser pour remettre à zéro les quotas d’un environnement réel.

L’étape 7 ajoutera les conversations et leur historique persistant. Les essais
Vercel, le stockage managé et la qualification finale restent au jalon regroupé.
