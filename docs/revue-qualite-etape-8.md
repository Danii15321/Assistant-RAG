# Revue du nouveau lot final — Étape 8

Statut : analyse par l’agent relue et validée par le porteur le 13 octobre 2026 (« Je valide la grille après lecture »).

La spécification §10.2 exige une grille humaine pour l’exactitude et la fidélité. Chaque réponse réelle, ses éléments attendus et ses citations figurent ci-dessous. Le premier lot final en échec reste conservé. Le nouveau lot a été réservé avant le gel de la version v5.

Bilan proposé : Recall@5 100 % (8 questions, 10 passages sur 10), exactitude 8/8, abstention 2/2. Toutes les affirmations ci-dessous sont étayées selon l’analyse de l’agent. H04 ajoute une comparaison correcte mais non demandée ; les citations PDF sont parfois larges.

## Grille à relire

### H01 — Dans quelle ville se trouve la médiathèque Aurore et quand ouvre-t-elle le samedi ?

Attendu : Dijon, 9 heures, 13 heures.

**Réponse :** La médiathèque Aurore se trouve à Dijon et ouvre le samedi de 9 h à 13 h.

Source S1 — aurore.pdf (page 1–1) :

> La médiathèque Aurore se trouve à Dijon. Elle ouvre le samedi de 9 heures à 13 heures. La salle de lecture Aurore porte le numéro C245. Elle propose 18 places assises. Les prêts Aurore sont réservés aux adhérents munis de leur carte. Chaque prêt dure deux semaines. Les ateliers Aurore ont lieu le mercredi de 15 heures à 17 heures. Les inscriptions se font sur place.

Analyse de l’agent : conforme aux éléments attendus ; sources fidèles.

### H02 — Sur quel port écoute le service HTTPS du laboratoire Sillage ?

Attendu : 10443.

**Réponse :** Le service HTTPS du laboratoire Sillage écoute sur le port 10443.

Source S1 — sillage.txt (line 1–1) :

> Le service HTTPS du laboratoire Sillage écoute sur le port 10443. Les postes de démonstration utilisent un réseau isolé.

Analyse de l’agent : conforme aux éléments attendus ; sources fidèles.

### H03 — Qui assure la coordination du programme Lys ?

Attendu : Nora Perrin.

**Réponse :** La coordination du programme Lys est assurée par Nora Perrin.

Source S1 — lys-2027.docx (paragraph 1–4) :

> Programme Lys 2027 : la coordination est assurée par Nora Perrin.

Analyse de l’agent : conforme aux éléments attendus ; sources fidèles.

### H04 — Combien de personnes peuvent composer une équipe Lys et que faut-il remettre à quelle date ?

Attendu : quatre maximum, 23 avril 2027, rapport huit pages maximum, affiche PDF.

**Réponse :** Une équipe Lys peut comporter au maximum quatre personnes.

Source S1 — lys-2027.docx (paragraph 1–4) :

> Les équipes du projet Lys comportent quatre personnes au maximum.

**Réponse :** Le projet Lys doit être remis le 23 avril 2027 avec un rapport de huit pages maximum et une affiche au format PDF.

Source S1 — lys-2027.docx (paragraph 1–4) :

> Le projet Lys doit être remis le 23 avril 2027. Le dossier contient un rapport de huit pages maximum et une affiche au format PDF.

**Réponse :** La politique Lys 2026 (15 jours de conservation) a été remplacée le 14 février 2027 par la politique Lys 2027 (65 jours).

Source S1 — lys-2027.docx (paragraph 1–4) :

> La politique Lys du 14 février 2027 conserve les fichiers pendant 65 jours après la remise. Elle remplace la politique Lys 2026.

Source S2 — lys-2026.txt (line 1–1) :

> La politique Lys 2026 conservait les fichiers pendant 15 jours après la remise. Cette règle a été remplacée le 14 février 2027.

Analyse de l’agent : conforme aux éléments attendus ; sources fidèles.

### H05 — Quelle conservation des fichiers est prévue par les politiques Lys 2026 et 2027, et quand la nouvelle remplace-t-elle l’ancienne ?

Attendu : 65 jours, 15 jours, 14 février 2027, la politique 2027 remplace celle de 2026.

**Réponse :** La politique Lys 2026 conservait les fichiers pendant 15 jours après la remise.

Source S1 — lys-2026.txt (line 1–1) :

> La politique Lys 2026 conservait les fichiers pendant 15 jours après la remise. Cette règle a été remplacée le 14 février 2027.

**Réponse :** La politique Lys du 14 février 2027 conserve les fichiers pendant 65 jours après la remise.

Source S2 — lys-2027.docx (paragraph 1–4) :

> La politique Lys du 14 février 2027 conserve les fichiers pendant 65 jours après la remise. Elle remplace la politique Lys 2026.

**Réponse :** La nouvelle politique du 14 février 2027 a remplacé la politique Lys 2026 à cette même date.

Source S1 — lys-2026.txt (line 1–1) :

> La politique Lys 2026 conservait les fichiers pendant 15 jours après la remise. Cette règle a été remplacée le 14 février 2027.

Source S2 — lys-2027.docx (paragraph 1–4) :

> La politique Lys du 14 février 2027 conserve les fichiers pendant 65 jours après la remise. Elle remplace la politique Lys 2026.

Analyse de l’agent : conforme aux éléments attendus ; sources fidèles.

### H06 — Quel jour et à quelles heures ont lieu les ateliers Aurore ?

Attendu : mercredi, 15 heures, 17 heures.

**Réponse :** Les ateliers Aurore ont lieu le mercredi de 15 h à 17 h.

Source S1 — aurore.pdf (page 1–1) :

> La médiathèque Aurore se trouve à Dijon. Elle ouvre le samedi de 9 heures à 13 heures. La salle de lecture Aurore porte le numéro C245. Elle propose 18 places assises. Les prêts Aurore sont réservés aux adhérents munis de leur carte. Chaque prêt dure deux semaines. Les ateliers Aurore ont lieu le mercredi de 15 heures à 17 heures. Les inscriptions se font sur place.

Analyse de l’agent : conforme aux éléments attendus ; sources fidèles.

### H07 — Et combien de places assises propose-t-elle ?

Attendu : 18.

Contexte du suivi : Quelle est la salle de lecture de la médiathèque Aurore ?

**Réponse :** La salle de lecture Aurore (numéro C245) propose 18 places assises.

Source S1 — aurore.pdf (page 1–1) :

> La médiathèque Aurore se trouve à Dijon. Elle ouvre le samedi de 9 heures à 13 heures. La salle de lecture Aurore porte le numéro C245. Elle propose 18 places assises. Les prêts Aurore sont réservés aux adhérents munis de leur carte. Chaque prêt dure deux semaines. Les ateliers Aurore ont lieu le mercredi de 15 heures à 17 heures. Les inscriptions se font sur place.

Analyse de l’agent : conforme aux éléments attendus ; sources fidèles.

### H08 — Quelles conditions faut-il remplir pour emprunter à Aurore et combien de temps dure un prêt ?

Attendu : adhérent, carte, deux semaines.

**Réponse :** Pour emprunter à Aurore, il faut être adhérent et présenter sa carte.

Source S1 — aurore.pdf (page 1–1) :

> La médiathèque Aurore se trouve à Dijon. Elle ouvre le samedi de 9 heures à 13 heures. La salle de lecture Aurore porte le numéro C245. Elle propose 18 places assises. Les prêts Aurore sont réservés aux adhérents munis de leur carte. Chaque prêt dure deux semaines. Les ateliers Aurore ont lieu le mercredi de 15 heures à 17 heures. Les inscriptions se font sur place.

**Réponse :** Chaque prêt dure deux semaines.

Source S1 — aurore.pdf (page 1–1) :

> La médiathèque Aurore se trouve à Dijon. Elle ouvre le samedi de 9 heures à 13 heures. La salle de lecture Aurore porte le numéro C245. Elle propose 18 places assises. Les prêts Aurore sont réservés aux adhérents munis de leur carte. Chaque prêt dure deux semaines. Les ateliers Aurore ont lieu le mercredi de 15 heures à 17 heures. Les inscriptions se font sur place.

Analyse de l’agent : conforme aux éléments attendus ; sources fidèles.

### H09 — Quel est le numéro de téléphone de la personne qui coordonne Lys ?

Attendu : information absente.

**Résultat :** abstention explicite, aucune affirmation factuelle. Appel Groq : oui.

Analyse de l’agent : conforme aux éléments attendus ; sources fidèles.

### H10 — Quelle température fera-t-il demain à la médiathèque Aurore ?

Attendu : information absente.

**Résultat :** abstention explicite, aucune affirmation factuelle. Appel Groq : oui.

Analyse de l’agent : conforme aux éléments attendus ; sources fidèles.

## Portée

Petit corpus fictif CC0 : ces résultats ne garantissent pas les performances sur des documents longs, techniques ou mal extraits. Corpus et revue initiale produits par le même agent ; pas d’audit indépendant. La validation humaine ne peut pas être déduite des tests automatisés.
