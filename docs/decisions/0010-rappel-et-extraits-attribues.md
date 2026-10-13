# ADR 0010 — Rappel documentaire et extraits attribués par le serveur

Date : 13 octobre 2026. Acceptation de poursuivre la correction demandée par le
porteur après présentation de l’échec du premier lot final.

## Constat

La première qualification finale obtient 62,5 % de Recall@5 et 50 % de réponses
complètes. Trois questions répondables sont rejetées faute de passage au-dessus
du seuil ; une sortie du modèle est rejetée pour citations invalides. Ce rapport
reste conservé et ses cas ne sont pas rejoués pour améliorer artificiellement le score.
La réponse brute refusée n’a pas été journalisée : sa cause précise (citation
réécrite, identifiant ou nombre non étayé) ne peut pas être affirmée a posteriori.

## Décision

La calibration utilise exclusivement les vingt questions de développement
initiales. Elle maximise d’abord le rappel, puis le rejet hors corpus et enfin
le seuil. Le nouveau calcul avec E5 réel retrouve **100 %** des passages annotés
à **0,81**, au lieu de privilégier le rejet d’une seule question hors corpus au
seuil 0,84. Les cas finaux ne participent pas au calcul. Le LLM doit décider de
l’abstention lorsque des passages voisins ne répondent pas à la question.

Le serveur divise les passages retenus en extraits exacts de 400 caractères
maximum et leur attribue les identifiants E1, E2… dans chaque source S1, S2…
Le modèle choisit les identifiants au lieu de recopier des citations libres.
Le serveur résout les identifiants, restitue les octets du texte extrait et
continue de contrôler les nombres et les références. Un identifiant inconnu
est refusé. Les payloads historiques à citations exactes restent validables,
mais le schéma strict envoyé à Groq demande les nouveaux identifiants.

L’API publique, les sources persistées et les interfaces restent compatibles ;
aucune migration de données ou réindexation n’est nécessaire. Le prompt est
versionné `grounded-claims-v5` et le budget demeure 2 500 + 600 tokens.

Un diagnostic borné sur Q16 (développement uniquement) a reproduit le rejet :
une affirmation citait la phrase de remplacement, mais son nombre figurait dans
la phrase précédente. La version v5 conserve les phrases d'un même paragraphe
ensemble, toujours dans la limite de 400 caractères. Un test reproduit l'échec
avant correction et vérifie qu'un nombre absent reste refusé. L'appel réel de
développement devient valide, mais omet encore d'expliciter la date de remplacement :
cette réponse reste partielle. Le lot réservé décidera de la conformité globale.

## Nouvelle validation

Quatre nouveaux documents fictifs CC0 et dix questions sont réservés dans
`evaluation/holdout-v2/`. Les faits sont distincts et certaines valeurs tirées
aléatoirement. Leurs empreintes sont enregistrées avant les essais. Ce lot ne
sert pas à choisir le seuil ou le prompt. Il est produit par le même agent et
ne constitue pas un audit humain externe. Les deux rapports finaux resteront
publiés ; le nouveau ne remplace pas l’échec initial.

Les identifiants prouvent la traçabilité, pas la fidélité sémantique. La revue des
affirmations, l’abstention hors corpus, les quotas et les performances restent
obligatoires. Abaisser le seuil peut augmenter le nombre d’appels Groq ; les
plafonds partagés ne sont ni augmentés ni réinitialisés pour les essais.
