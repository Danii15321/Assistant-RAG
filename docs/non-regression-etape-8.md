# Non-régression v7 — Étape 8

Analyse de l’agent du 13 octobre 2026. Le lot était déjà ouvert : cette exécution ne remplace pas le lot indépendant v5 ni sa validation humaine. Aucun réglage ne suit ces résultats.

**Bilan :** Recall@5 8/8 (10/10 passages), réponses complètes 7/8 (87,5 %), abstention 2/2 ; 13/13 affirmations fidèles, 15/15 références valides. Aucune erreur technique. H04 est incomplet et compte comme tel.

## H01 — Dans quelle ville se trouve la médiathèque Aurore et quand ouvre-t-elle le samedi ?

Attendu : Dijon, 9 heures, 13 heures.

**Réponse :** La médiathèque Aurore se trouve à Dijon et ouvre le samedi de 9 h à 13 h.

S1 :

> La médiathèque Aurore se trouve à Dijon. Elle ouvre le samedi de 9 heures à 13 heures. La salle de lecture Aurore porte le numéro C245. Elle propose 18 places assises. Les prêts Aurore sont réservés aux adhérents munis de leur carte. Chaque prêt dure deux semaines. Les ateliers Aurore ont lieu le mercredi de 15 heures à 17 heures. Les inscriptions se font sur place.

Analyse : éléments attendus couverts, affirmations étayées.

## H02 — Sur quel port écoute le service HTTPS du laboratoire Sillage ?

Attendu : 10443.

**Réponse :** Le service HTTPS du laboratoire Sillage écoute sur le port 10443.

S1 :

> Le service HTTPS du laboratoire Sillage écoute sur le port 10443. Les postes de démonstration utilisent un réseau isolé.

Analyse : éléments attendus couverts, affirmations étayées.

## H03 — Qui assure la coordination du programme Lys ?

Attendu : Nora Perrin.

**Réponse :** La coordination du programme Lys est assurée par Nora Perrin.

S1 :

> Programme Lys 2027 : la coordination est assurée par Nora Perrin.

Analyse : éléments attendus couverts, affirmations étayées.

## H04 — Combien de personnes peuvent composer une équipe Lys et que faut-il remettre à quelle date ?

Attendu : quatre maximum, 23 avril 2027, rapport huit pages maximum, affiche PDF.

**Réponse :** Une équipe Lys peut comporter quatre personnes au maximum.

S1 :

> Les équipes du projet Lys comportent quatre personnes au maximum.

**Réponse :** Le projet Lys doit être remis le 23 avril 2027.

S1 :

> Le projet Lys doit être remis le 23 avril 2027. Le dossier contient un rapport de huit pages maximum et une affiche au format PDF.

**Réponse :** La politique Lys 2026, qui conservait les fichiers 15 jours, a été remplacée le 14 février 2027.

S2 :

> La politique Lys 2026 conservait les fichiers pendant 15 jours après la remise. Cette règle a été remplacée le 14 février 2027.

S1 :

> La politique Lys du 14 février 2027 conserve les fichiers pendant 65 jours après la remise. Elle remplace la politique Lys 2026.

Analyse : incomplet ; rapport de huit pages maximum et affiche PDF omis, comparaison supplémentaire étayée.

## H05 — Quelle conservation des fichiers est prévue par les politiques Lys 2026 et 2027, et quand la nouvelle remplace-t-elle l’ancienne ?

Attendu : 65 jours, 15 jours, 14 février 2027, la politique 2027 remplace celle de 2026.

**Réponse :** La politique Lys 2026 prévoyait de conserver les fichiers pendant 15 jours après la remise.

S1 :

> La politique Lys 2026 conservait les fichiers pendant 15 jours après la remise. Cette règle a été remplacée le 14 février 2027.

**Réponse :** La politique Lys 2027, entrée en vigueur le 14 février 2027, conserve les fichiers pendant 65 jours après la remise.

S2 :

> La politique Lys du 14 février 2027 conserve les fichiers pendant 65 jours après la remise. Elle remplace la politique Lys 2026.

**Réponse :** La politique Lys 2027 a remplacé la politique Lys 2026 le 14 février 2027.

S1 :

> La politique Lys 2026 conservait les fichiers pendant 15 jours après la remise. Cette règle a été remplacée le 14 février 2027.

S2 :

> La politique Lys du 14 février 2027 conserve les fichiers pendant 65 jours après la remise. Elle remplace la politique Lys 2026.

Analyse : éléments attendus couverts, affirmations étayées.

## H06 — Quel jour et à quelles heures ont lieu les ateliers Aurore ?

Attendu : mercredi, 15 heures, 17 heures.

**Réponse :** Les ateliers Aurore ont lieu le mercredi de 15 h à 17 h.

S1 :

> La médiathèque Aurore se trouve à Dijon. Elle ouvre le samedi de 9 heures à 13 heures. La salle de lecture Aurore porte le numéro C245. Elle propose 18 places assises. Les prêts Aurore sont réservés aux adhérents munis de leur carte. Chaque prêt dure deux semaines. Les ateliers Aurore ont lieu le mercredi de 15 heures à 17 heures. Les inscriptions se font sur place.

Analyse : éléments attendus couverts, affirmations étayées.

## H07 — Et combien de places assises propose-t-elle ?

Attendu : 18.

**Réponse :** La salle de lecture C245 de la médiathèque Aurore propose 18 places assises.

S1 :

> La médiathèque Aurore se trouve à Dijon. Elle ouvre le samedi de 9 heures à 13 heures. La salle de lecture Aurore porte le numéro C245. Elle propose 18 places assises. Les prêts Aurore sont réservés aux adhérents munis de leur carte. Chaque prêt dure deux semaines. Les ateliers Aurore ont lieu le mercredi de 15 heures à 17 heures. Les inscriptions se font sur place.

Analyse : éléments attendus couverts, affirmations étayées.

## H08 — Quelles conditions faut-il remplir pour emprunter à Aurore et combien de temps dure un prêt ?

Attendu : adhérent, carte, deux semaines.

**Réponse :** Pour emprunter à Aurore, il faut être adhérent et posséder sa carte.

S1 :

> La médiathèque Aurore se trouve à Dijon. Elle ouvre le samedi de 9 heures à 13 heures. La salle de lecture Aurore porte le numéro C245. Elle propose 18 places assises. Les prêts Aurore sont réservés aux adhérents munis de leur carte. Chaque prêt dure deux semaines. Les ateliers Aurore ont lieu le mercredi de 15 heures à 17 heures. Les inscriptions se font sur place.

**Réponse :** Chaque prêt dure deux semaines.

S1 :

> La médiathèque Aurore se trouve à Dijon. Elle ouvre le samedi de 9 heures à 13 heures. La salle de lecture Aurore porte le numéro C245. Elle propose 18 places assises. Les prêts Aurore sont réservés aux adhérents munis de leur carte. Chaque prêt dure deux semaines. Les ateliers Aurore ont lieu le mercredi de 15 heures à 17 heures. Les inscriptions se font sur place.

Analyse : éléments attendus couverts, affirmations étayées.

## H09 — Quel est le numéro de téléphone de la personne qui coordonne Lys ?

Attendu : information absente.

Résultat : abstention explicite, avec appel Groq réel.

Analyse : éléments attendus couverts, affirmations étayées.

## H10 — Quelle température fera-t-il demain à la médiathèque Aurore ?

Attendu : information absente.

Résultat : abstention explicite, avec appel Groq réel.

Analyse : éléments attendus couverts, affirmations étayées.
