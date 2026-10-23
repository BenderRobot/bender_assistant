# Éditeurs graphiques de Bender

## Créer une bouche

1. Ouvrir le menu **Bouche**, choisir éventuellement une des 12 poses existantes.
2. Déplier **Créer ou modifier une bouche · éditeur graphique**.
3. Cliquer sur **Copier la pose sélectionnée** pour en faire une copie éditable.
4. Déplacer les points orange (ligne du haut) et verts (ligne du bas). La symétrie peut être activée ou désactivée. Les outils de dessin permettent de tracer directement chaque ligne.
5. Utiliser les réglages précis pour saisir les hauteurs, changer le nombre de séparations des dents, l'épaisseur des lignes, les dents arrondies ou le masquage inférieur.
6. Donner un nom, cliquer sur **Enregistrer**, puis **Tester dans l'atelier** ou **Afficher ma création**.

Les courbes sont conservées avec 121 échantillons sur la largeur utile du format 128 × 64. Le contour extérieur reste celui de la matrice existante. Le point central permet de modifier l'ouverture centrale sans changer les extrémités. Les lignes restent ordonnées ; les points peuvent toucher l'autre ligne sans la traverser.

## Créer des yeux

1. Ouvrir **Yeux**, sélectionner éventuellement une expression de départ.
2. Déplier **Créer ou modifier des yeux · éditeur graphique** puis copier l'expression choisie.
3. En mode **Paupières et pupilles**, déplacer les points orange/verts ou les centres bleus des pupilles.
4. En mode **Position et taille**, déplacer le centre de chaque œil et ses poignées de rayon.
5. Activer **Lier les deux yeux** pour reproduire les changements, ou sélectionner un œil pour travailler séparément.
6. Dans les réglages précis, ajuster positions, rayons, pupilles, paupières et couleur. Donner un nom et enregistrer.

Les copies des expressions sont paramétriques ; les poses originales restent intactes. Le format d'aperçu est 800 × 480, avec le cadre déjà utilisé par Bender.

## Bibliothèque et essais

- **Mes bouches / Mes yeux** : retrouver les créations du serveur, les afficher ou les charger pour modification.
- **Enregistrer** : créer une entrée ou modifier celle chargée.
- **Enregistrer une copie** : conserver la précédente et donner un autre nom à la nouvelle.
- **Annuler / Rétablir** : historique des modifications de forme dans l'éditeur, jusqu'à 60 états.
- **Exporter JSON** : exporter la géométrie et son nom pour une sauvegarde portable.
- **Tester dans l'atelier** : appliquer le dessin sur les aperçus et les fenêtres de visage connectées au serveur. Cette action arrête la lecture en cours.

Les yeux personnalisés peuvent être conservés pendant la lecture audio, y compris sur le Dell. Une bouche personnalisée s'affiche en prévisualisation manuelle ; la parole automatique continue à utiliser les 12 poses associées aux calages existants. L'association d'une nouvelle bouche à un visème n'est pas modifiée automatiquement par l'éditeur.

Choisir une expression ou une bouche d'origine revient aux formes d'origine. Changer seulement le comportement ou le clignement conserve les yeux personnalisés.

## Sauvegarde

Les créations sont dans `data/poses.sqlite3` sur Bender, hors du dépôt Git et conservées par les mises à jour du code. Sauvegarder ce fichier avec les autres données personnelles du projet. Le chemin peut être changé avec `BENDER_POSES_DB`.

Les formes sont validées par le serveur : coordonnées bornées et finies, deux yeux, longueurs de courbes fixes, noms limités. Aucun code SVG/HTML/JavaScript n'est enregistré comme dessin. La modification d'une création obsolète dans un autre onglet est refusée pour éviter un écrasement silencieux.

## Vérifications

33 tests passent : les créations bouche et yeux survivent à la réouverture de l'application, les conflits de révision sont détectés, les formes invalides et écritures provenant d'une autre origine sont refusées. Les formes personnalisées transitent par le WebSocket du visage et les yeux sont transmis pendant la lecture du Dell.

Les 12 copies de bouches et les 13 bases d'expressions ont été validées contre le schéma. Les déplacements de poignées, Annuler/Rétablir et l'enregistrement des deux types ont été vérifiés dans le navigateur. La base de prévisualisation locale est distincte de la bibliothèque réelle à déployer.
