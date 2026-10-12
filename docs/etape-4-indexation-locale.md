# Étape 4 — Découpage et indexation locale

**Validée en local le 11 octobre 2026.** Budget : **0 €** ; aucun appel Groq,
déploiement ou service cloud provisionné.

## Fonctionnement livré

L’import PDF/DOCX/TXT enchaîne extraction, découpage, embeddings et publication.
La bibliothèque affiche la progression des passages et l’état « Prêt », puis
permet de consulter les passages avec leur texte et leurs repères de début/fin.
Le texte extrait reste consultable indépendamment du résultat d’indexation.

Les passages sont privés. Leur consultation utilise l’identité vérifiée et les
mêmes contrôles d’origine, de session et d’isolation que l’import. L’API refuse
un autre propriétaire avec la même 404 qu’un document inexistant. Aucune donnée
privée n’est mise en cache ; les vecteurs ne sont pas retournés au navigateur.

## Paramètres figés

| Paramètre | Valeur |
| --- | --- |
| Modèle | `intfloat/multilingual-e5-small` |
| Révision | `614241f622f53c4eeff9890bdc4f31cfecc418b3` |
| Dimension / calcul | 384 / CPU, un thread PyTorch |
| Préfixes | `passage: ` et `query: ` |
| Normalisation | L2, norme vérifiée à ±0,001 |
| Budget de passage | 300 tokens du tokenizer E5, avant préfixe |
| Chevauchement | 50 tokens ; progression garantie aux frontières |
| Limite modèle | 512 tokens, préfixe et tokens spéciaux compris |
| Frontières | Paragraphes puis phrases, dans la seconde moitié du budget |
| Allocation texte | Fenêtre de 32 768 caractères par passage ; dépassement inexploitable refusé |
| Lot | Au maximum 16 passages |
| Démarrage / calcul / bail | 90 / 45 / 120 secondes |
| Worker local | 1,5 Gio, un travail global à la fois |
| Quotas partagés | 10 000 passages par compte / 20 000 globaux |

Les unités canoniques sont jointes par `\n\n`. Les offsets désignent des caractères
dans cette chaîne, pas des octets du fichier. Les passages conservent une tranche
exacte : caractères Unicode, ponctuation et espaces ne sont pas régénérés.
Les numéros physiques PDF, paragraphes DOCX et lignes TXT restent ceux de
l’extraction, y compris les trous correspondant à des unités vides.

La configuration d’index garde modèle, révision, dimension, préfixes, normalisation
et version de découpage. Le document conserve également la version du parseur.
L’adaptateur des questions utilise exactement le même modèle et les mêmes
contrôles de longueur et de normalisation ; la recherche n’est pas encore exposée.
Les conventions du modèle suivent sa [fiche officielle](https://huggingface.co/intfloat/multilingual-e5-small) et l’[API Sentence Transformers](https://www.sbert.net/docs/package_reference/sentence_transformer/model.html).
Voir [ADR 0005](decisions/0005-indexation-locale-reprenable.md).

## Reprise, publication et quotas

La préparation réserve le quota et insère manifeste/passages en une transaction.
Le calcul se fait hors transaction. Chaque lot validé enregistre ses vecteurs et
son compteur avant de réarmer le travail. Une interruption avant ce commit fait
recalculer ce lot ; après le commit, seuls les passages sans vecteur sont repris.
La contrainte unique document/génération/ordre exclut les doublons.

Une indexation partielle reste `processing` et ne retourne aucun passage publié.
Le dernier commit passe le document à `ready`. Les lectures imposent dans SQL
le propriétaire, la génération et la version compatible. Un bail remplacé ou une
suppression pendant le calcul bloque l’écriture du résultat.

Trois erreurs consécutives laissent le document en échec explicite. « Relancer »
préserve les checkpoints d’indexation et réarme le même travail. Les passages
réservés d’un document échoué continuent de compter dans le quota pour éviter
son contournement. La suppression nettoie original, unités, manifeste et vecteurs.
Le plafond de base de 600 Mio arrête une nouvelle préparation.

## Reproduction

Consulter le [guide local](developpement-local.md) pour l’installation et le
téléchargement initial gratuit du modèle public. Ensuite, le traitement est hors
ligne et ne dépend d’aucune clé API LLM.

```bash
bash scripts/local/check.sh
docker compose stop worker
python3 scripts/local/qualify_indexation.py
docker compose up -d worker
```

Faire la mesure E5 seule, après le build et les tests navigateur. La mémoire WSL
et les autres programmes peuvent augmenter les durées ; les valeurs locales ne
préjugent pas des performances Vercel. Le rapport distingue chargement, premier
lot, lot chaud et coût du processus isolé avec un lot réel de 16 passages proches
de 300 tokens. Les textes du corpus sont également encodés avec leurs repères
vérifiés. Les questions réservées à la validation ne sont pas utilisées.

## Mesures CPU réelles

[Rapport de l’adaptateur utilisé par le worker](../evaluation/reports/index-step4-resident-embeddings.json),
exécuté dans un conteneur **sans réseau** : quatre fichiers du corpus, 17 unités
et cinq passages ; encodage réel des passages et questions avec le même processus.

| Mesure locale | Résultat |
| --- | --- |
| Lot représentatif | 16 passages, au plus 303 tokens avec préfixe/tokens spéciaux |
| Démarrage et premier lot | 49,336 s |
| Lot suivant, modèle conservé | 5,272 s |
| Pic RSS du processus d’encodage | 963,4 Mio |
| Fichiers du modèle et manifeste | 492 796 264 octets |

Le modèle reste chargé entre lots dans un processus privé. Une erreur ou un
blocage ferme ce processus ; le lot est repris avec un nouveau processus et un
nouveau bail. Le démarrage a une limite de 90 secondes, les calculs suivants de
45 secondes ; chaque bail d’indexation dure 120 secondes. Le bail d’extraction
reste à 60 secondes, avec ses limites initiales de parseur.

Le [premier essai avec chargement par lot](../evaluation/reports/index-step4-embeddings.json)
avait mesuré 42,770 secondes par processus complet et environ six secondes de
calcul chaud. Ce coût répété a dépassé le timeout pendant le parcours navigateur,
ce qui justifie le modèle conservé en mémoire. Les mesures ci-dessus qualifient
l’implémentation retenue. Le démarrage et les ressources Vercel restent à vérifier
au jalon regroupé ; les durées locales proviennent d’une machine WSL partagée.

## Migration et persistance

**77 tests réussis** : deux tests de bootstrap, 38 tests backend, 17 tests
PostgreSQL et 20 parcours Chromium sur bureau/mobile. Ruff, formatage, mypy,
ESLint, TypeScript et build Next.js passent. Les parcours utilisent E5 réel,
vérifient dimensions/normes dans PostgreSQL, texte exact/repères dans l’API,
isolation de deux comptes et envoi direct réel de 20 Mio.
[Rapport de validation locale](../evaluation/reports/index-step4-local.json).

Captures vérifiées : [bureau](../evaluation/reports/step4-desktop.png) et
[mobile](../evaluation/reports/step4-mobile.png).

`0004_indexes` ne modifie ni les migrations déjà appliquées, ni les comptes,
originaux ou unités d’extraction. Elle met les documents `processing/extracted`
existants en file d’indexation. La base de test vérifie ce passage depuis l’ancien
schéma et la réapplication sans doublon.

Avant toute migration de production, sauvegarder PostgreSQL et les originaux
privés ensemble. Le downgrade 0004 détruit les manifestes, passages et vecteurs
et repasse les indexations prêtes, partielles ou échouées à `processing/extracted` ; les originaux et unités
restent conservés. Un retour vers le code de l’étape 3 doit accompagner ce retour
de schéma. Ces essais de downgrade sont limités à la base locale isolée.

Le contrôle de remplacement des services compare les empreintes des originaux,
unités et vecteurs avec les versions et compteurs. Il utilise exclusivement la
base `assistant_rag_test` et son volume privé. Le remplacement de PostgreSQL
conserve son volume, comme à l’étape 1.

[Rapport de persistance](../evaluation/reports/index-step4-persistence.json) :
les dix documents de test conservent leurs octets, textes et vecteurs après
remplacement des services. Le prototype Vercel de l’étape 0 reste inchangé.
La recherche de secrets dans les sources, documents, rapports et bundle public
ne trouve aucune des cinq valeurs de secrets configurées localement.

## Limites et suite

La recherche, Recall@5, les questions et les réponses sourcées ne sont pas encore
livrées. La pertinence du découpage sera évaluée à l’étape 5 sans modifier le lot
final réservé. Le modèle résident, la concurrence et les limites réelles de
Container/Queues seront qualifiés au prochain jalon Vercel, sans déploiement
automatique au fil des implémentations locales.
