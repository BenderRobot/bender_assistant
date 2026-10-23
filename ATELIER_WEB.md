# Atelier Bender — menus

La page d'accueil propose cinq onglets accessibles directement :

- `/#yeux` : 13 expressions, comportement et clignement de démonstration.
- `/#bouche` : 12 poses existantes, dents droites/arrondies et défilement de démonstration.
- `/#voix` : extraits enregistrés, bibliothèque de répliques et synthèse à partir du texte.
- `/#reconnaissance` : microphone du Dell, transcription locale, diagnostic et aide Vosk.
- `/#cerveau` : connexion du compte ChatGPT, choix du modèle et test texte ([guide](CERVEAU_GPT.md)).
- `/#vision` : capture LifeCam et analyse explicite avec GPT.

Les aperçus des yeux et de la bouche restent visibles. La clé et la sortie audio sont dans « Connexion au Dell », disponible depuis tous les onglets. Pour écouter sans clé matérielle, choisir « Ce navigateur ». Les écrans `/face?display=eyes` et `/face?display=mouth` restent compatibles.

Les menus Yeux et Bouche incluent maintenant leurs éditeurs graphiques et leurs bibliothèques de créations personnelles. Voir [EDITEURS_GRAPHIQUES.md](EDITEURS_GRAPHIQUES.md) pour le dessin à la souris, les copies de poses, les réglages et la sauvegarde.

## Enregistrements retrouvés

Les cinq extraits du banc d'essai et la réplique « Un déguisement ringard… » sont préparés depuis le dossier centralisé `banc_essai`. Les autres fichiers bruts restent dans `bender voice sample` ; cette page affiche les six références préparées et les entrées activées du catalogue de bibliothèque du serveur.

Le script `scripts/prepare-reference-samples.py` copie les références dans `data/reference_samples` et conserve les calages existants. Les calages visuels sont disponibles pour Noël, Fauteuil et la réplique ; les autres extraits ont leurs anciens phonèmes estimés et peuvent utiliser l'estimation acoustique. Ces repères restent provisoires.

Le lanceur de mise à jour prépare une archive de références séparée du code et la transfère par SSH. Les WAV restent hors de GitHub. Debian valide l'archive comme données audio/JSON avant de l'installer ; les samples personnels et configurations ne sont pas remplacés. Sur un autre PC, conserver aussi `banc_essai` ou les références préparées dans `data/reference_samples` si leur transfert est souhaité.

La bibliothèque de répliques ajoutées via l'outil `bender_voice import` apparaît à côté des extraits et peut être lue explicitement, sans dépendre du tirage contextuel. Les fichiers bruts ne sont pas importés automatiquement comme répliques de conversation.

## Reconnaissance vocale

Le diagnostic distingue le périphérique audio, l'outil arecord et la présence du modèle Vosk. Un modèle absent nécessite le téléchargement indiqué dans l'aide du menu ; l'ajout des menus ne déclenche pas ce téléchargement. La transcription est locale, l'appel au cerveau GPT est optionnel et nécessite Internet.

## Validation

30 tests passent. Les tests couvrent notamment la préparation d'un extrait sans synthèse, la lecture de son audio et de son calage, ainsi que le refus d'archives de références contenant des traversées de chemins, des liens ou des fichiers de catalogue manquants. Navigation, choix de pose et lecture d'un extrait avec calage visuel ont aussi été vérifiés dans le navigateur local.
