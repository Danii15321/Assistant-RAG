# Étape 3 — Import privé et extraction locale

## Parcours disponible

Créer un compte ou se connecter, ouvrir `/library`, choisir PDF textuel, DOCX ou
TXT UTF-8 et cliquer sur **Importer**. Plusieurs fichiers sont envoyés successivement.
La bibliothèque affiche l’attente et l’extraction, puis **Texte extrait** ou une
explication d’échec. **Voir le texte** ouvre les unités avec leurs repères ;
**Relancer** reprend un échec ; **Supprimer** exclut immédiatement le document et
confie le nettoyage au worker.

Les pages PDF sont numérotées physiquement, y compris lorsqu’une page précédente
est vide. Les paragraphes DOCX comprennent les cellules de tableaux simples dans
l’ordre du XML. Les lignes TXT gardent leurs numéros, même avec des lignes vides.
BOM UTF-8 accepté. Les espaces extérieurs et caractères de contrôle sont normalisés ;
le texte canonique affiché est celui conservé pour le découpage futur. Certains
PDF complexes et tableaux Word fusionnés peuvent nécessiter une extraction plus
riche ultérieurement ; aucun OCR ou téléchargement de ressources externes.

L’extraction n’est pas encore l’indexation : `processing/extracted` est un état
intermédiaire explicite. Aucun document n’est `ready` ni recherchable à cette étape.

## Frontières privées

1. Next.js vérifie la session et transmet au backend un JWT créé côté serveur.
2. FastAPI déduit le propriétaire, réserve l’objet et délivre une capacité courte.
3. Le navigateur envoie les octets directement au backend local, avec cette
   capacité dans un en-tête. Aucun fichier ne traverse le proxy Next.js.
4. La finalisation vérifie taille réelle, objet réservé et empreinte serveur.
5. La transaction crée le travail durable ; le worker extrait et publie le texte.

Listes, détails, extraction, relances et suppressions sont filtrés par propriétaire.
Une ressource inconnue ou appartenant à un autre compte renvoie `404`. Les objets
n’ont aucune route de téléchargement public, ni URL permanente. La capacité est
consommée à l’envoi, expire en dix minutes et cesse de fonctionner à la déconnexion.
Elle ne sert pas de session utilisateur et ne figure pas dans l’URL ou localStorage.
Réponses privées `no-store`, CORS limité à l’origine frontend configurée et méthodes
autorisées. Les mutations via Next.js exigent l’origine exacte.

## Limites du pilote

| Limite | Valeur locale |
| --- | --- |
| Original | 20 Mio, `MAX_FILE_BYTES` configurable côté API |
| Réservation et capacité | 10 minutes |
| Envoi | 120 secondes |
| Extraction | 30 secondes murales, 20 secondes CPU, 512 Mio mémoire |
| DOCX | 50 Mio décompressés, 2 000 entrées ZIP, sans chiffrement/DTD/entités |
| PDF | 500 pages, non chiffré, texte obligatoire |
| Texte canonique | 2 000 000 caractères, 10 000 repères, 64 Kio UTF-8 par repère |
| Bibliothèque | 50 documents / 100 Mio par compte |
| Ensemble local | 100 documents / 600 Mio d’originaux réservés ou conservés |
| Base | Nouvel import refusé à 600 Mio réellement occupés |
| Traitements | Un travail simultané, bail 60 s, trois tentatives d’extraction |

La limite d’envoi ne garantit pas l’acceptation d’un contenu dépassant les limites
d’extraction. Le cas vérifié de 20 Mio contient un texte court et un remplissage
blanc. Les réservations occupent immédiatement le quota ; les documents à supprimer
le libèrent après nettoyage. Les compteurs et verrous sont partagés dans PostgreSQL.

## Reprise et nettoyage

`documents`, `extracted_units` et `ingestion_jobs` sont créées par
`0003_documents`. Les FK composites empêchent des unités/travaux d’un propriétaire
différent. SHA-256 est unique par compte hors documents en suppression.
La finalisation répétée ou le travail livré plusieurs fois ne crée pas plusieurs
extractions. Une relance incrémente la génération ; une ancienne génération ou un
ancien bail ne peut plus publier. Publication des unités et mise à jour du document
se font dans une seule transaction.

Un upload abandonné expire et devient un travail de suppression. Les fichiers
partiels et objets orphelins âgés de plus d’une heure sont collectés. La suppression
masque immédiatement le document, puis retire original, unités et travaux. Une
répétition avant nettoyage est acceptée ; après nettoyage, `404` est indistinguable
d’une ressource inconnue. Un traitement concurrent ne peut recréer son contenu.

Le volume `assistant-rag_private_files` contient les originaux, UUID uniquement,
répertoire `0700` et objets `0600`. Les tests utilisent le volume distinct
`assistant-rag_private_test_files` et exclusivement `assistant_rag_test`.

## Vérification reproductible

```bash
python3 scripts/local/bootstrap.py
docker compose up --build -d --wait
bash scripts/local/check.sh
```

Les tests couvrent les trois formats, les repères, fichiers vides/corrompus/scannés,
UTF-8, chiffrement, XML hostile et limites de décompression/texte. PostgreSQL vérifie
l’isolation, les FK, les doublons, la publication répétée, les relances bornées,
les baux interrompus, la suppression concurrente, les uploads abandonnés et les
quotas concurrents. Chromium vérifie le parcours réel bureau/mobile, la capacité,
les origines et l’envoi direct de 20 Mio. Les contrôles de persistance recréent la
base locale et les services de test en conservant les volumes.

**Validation complète le 11 octobre 2026 : 59 tests réussis.**

| Contrôle | Résultat |
| --- | --- |
| Configuration locale | 2 tests |
| API/JWT/extraction | 28 tests |
| PostgreSQL/migrations/import | 9 tests |
| Chromium bureau/mobile | 20 tests, 6,9 minutes |
| Ruff, format, mypy, ESLint, TypeScript | Réussis |
| Build de production Next.js | Réussi |
| Persistance PostgreSQL | Conteneur recréé, vecteur conservé |
| Persistance des imports | 10 originaux et textes inchangés après remplacement API/worker |
| Secrets dans sources/docs/bundle public | 0 correspondance |
| Prototype de l’étape 0 | 4 fichiers inchangés |

[Rapport JSON](../evaluation/reports/import-step3.json) ·
[Persistance privée](../evaluation/reports/import-step3-persistence.json) ·
[Contrôles finaux](../evaluation/reports/import-step3-final-checks.json) ·
[Capture bureau](../evaluation/reports/step3-desktop.png) ·
[Capture mobile](../evaluation/reports/step3-mobile.png).
Les captures utilisent uniquement le corpus fictif Iris et des comptes de test.
Aucun appel LLM, abonnement, service managé ou déploiement Vercel. Blob privé,
upload direct Blob, Queues et HTTPS public restent réservés au jalon Vercel regroupé.

## Migration et retour arrière

Cette migration ajoute des tables, sans modifier comptes/sessions. Avant une future
migration de production, sauvegarder PostgreSQL et les originaux privés ensemble,
arrêter les consommateurs et conserver les versions de traitement. Une sauvegarde
DB seule ne restaure pas les fichiers. `alembic downgrade 0002_identity` supprime
les documents, textes et travaux : opération destructive, vérifiée uniquement sur
base de test, jamais un mécanisme automatique de rollback. Le volume de fichiers
reste à gérer séparément. Les comptes sont conservés à cette révision.

Le rollback applicatif doit rester compatible avec le schéma déployé ; l’application
ancienne vérifie une révision stricte et peut signaler `503` après migration. Prévoir
le couple code/schéma au jalon cloud. Ne jamais utiliser `down --volumes` pour les
contrôles locaux.
