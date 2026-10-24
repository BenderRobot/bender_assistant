# Atelier Bender — menus

La page s’ouvre sur **Discuter avec Bender** (`/#discuter`) : saisie de texte, démarrage du micro, fin d’écoute et journal sont regroupés. Les autres fonctions sont dans **Réglages et atelier**.

Deux encarts distinguent la configuration et le résultat :

- **Configuration du serveur** annonce si ElevenLabs est activé et permet de choisir le routage.
- **Audio de la dernière réponse** utilise la source effectivement renvoyée avec l’audio, indépendamment du moteur configuré.

Chaque échange conserve aussi sa source : **ElevenLabs · API**, **Chatterbox · local**, **Cache · ElevenLabs**, **Cache · Chatterbox**, **Réplique enregistrée** ou **Voix système · générique**. Une lecture depuis le cache ou le bouton Rejouer ne fait pas de nouvelle génération. Une erreur cloud ne sera donc pas présentée comme une réponse ElevenLabs si la voix système a pris le relais.

La source décrit l’audio préparé ; une éventuelle erreur des enceintes reste affichée séparément. Les durées GPT et préparation audio sont mesurées côté serveur. Pour une version ancienne sans ces mesures, le navigateur affiche seulement le temps total de préparation. Le diagnostic de voix est actualisé sans faire parler Bender ni consommer de crédits.

**Configurer la voix** ouvre directement ses réglages. Les bulletins, les enregistrements et les essais manuels sont repliables. Les éditeurs et les menus existants restent disponibles dans l’atelier.

Les onglets avancés restent accessibles directement :
- `/#yeux` : 13 expressions, comportement et clignement de démonstration.
- `/#bouche` : 12 poses existantes, dents droites/arrondies et défilement de démonstration.
- `/#voix` : extraits enregistrés, bibliothèque de répliques et synthèse à partir du texte.
- `/#reconnaissance` : durée maximale du micro, diagnostic et aide Vosk ; l’écoute se commande depuis Discuter.
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

135 tests passent, dont les contrôles de source réelle, de cache, de secours, de journal par échange et de compatibilité des commandes micro. Les tests couvrent notamment la préparation d'un extrait sans synthèse, la lecture de son audio et de son calage, ainsi que le refus d'archives de références contenant des traversées de chemins, des liens ou des fichiers de catalogue manquants. Navigation, choix de pose et lecture d'un extrait avec calage visuel ont aussi été vérifiés dans le navigateur local.

## Voir et piloter la conversation

Le journal commun affiche les transcriptions et les réponses de Bender. Dans Reconnaissance vocale, « Démarrer le micro du Dell » ouvre une prise ; « Pause et transcrire » la termine et déclenche la réponse si l’option automatique est cochée. Un mode manuel permet de corriger le texte avant l’envoi. Voir [MICRO_CONVERSATION.md](MICRO_CONVERSATION.md).

## Qualité de la caméra

Dans Caméra et vision, les captures attendent deux secondes de stabilisation et utilisent le MJPEG HD 1280 × 720 si la LifeCam le propose, avec repli VGA. Charger les réglages affiche les contrôles natifs disponibles. « Moins exposée » passe l’exposition en manuel et réduit son temps de 35 % ; « Plus exposée » l’augmente de 50 %. Chaque modification reprend une photo sans envoi à GPT. « Automatique » rétablit l’exposition et la balance des blancs automatiques disponibles, ainsi que luminosité/contraste/contre-jour d’usine. Les valeurs sont conservées dans `data/voice/hardware/camera-settings.json` (ou le data_dir configuré), hors Git.

Les détails des zones déjà saturées ne peuvent pas être récupérés sur la photo précédente : régler la caméra puis reprendre la vue. Le résultat réel doit être vérifié sur la LifeCam après déploiement. Principes des contrôles natifs : [documentation V4L2 du noyau Linux](https://docs.kernel.org/userspace-api/media/v4l/ext-ctrls-camera.html). Stabilisation par sélection des images : [documentation FFmpeg](https://www.ffmpeg.org/ffmpeg-filters.html#select_002c-aselect).

## Correction automatique avant GPT

Chaque capture reçoit une correction locale modérée, adaptée à son histogramme de luminance : contraste, luminosité et netteté légère. Le traitement Pillow est déterministe et ne génère aucun objet ou détail. La photo corrigée est affichée par défaut et envoyée à GPT ; le sélecteur « Image affichée » permet de comparer avec l’original. Le choix d’affichage ne change pas la version envoyée au cerveau. Aucun appel GPT supplémentaire n’est déclenché par la correction.

Même une demande directe à `/api/hardware/vision` repasse par cette préparation. Chaque correction repart de l’original ; elle n’est pas réappliquée sur une version déjà corrigée. Les originaux et leurs copies corrigées sont privés, accessibles avec la clé de contrôle, et supprimés par paires pour conserver les trois dernières captures. Les zones déjà uniformément blanches ou noires ne retrouvent pas leurs détails. Pillow est installé par la mise à jour habituelle.

Référence technique : [histogrammes et transformations de pixels Pillow](https://pillow.readthedocs.io/en/stable/reference/Image.html).

## Samples et personnalité

Le menu `/#samples` affiche les nouveaux sons et vidéos importés lors des mises à jour, leurs transcriptions Whisper locales, le classement GPT et les images de référence. Le moteur utilisé est affiché sur chaque transcription ; un bouton relance les anciens résultats Vosk, avec conservation du texte précédent. Les passages se valident comme réplique, candidat vocal ou repère bouche/yeux. Voir [SAMPLES_PERSONNALITE.md](SAMPLES_PERSONNALITE.md).


## Atelier avec visage a gauche et controle du deploiement

Les yeux et la bouche sont empiles dans la colonne de gauche. Les boutons de conversation et les menus de l'atelier sont directement dessous. Les reglages, la conversation et la source reelle de chaque audio apparaissent a droite. Sur petit ecran, la colonne passe au-dessus du contenu.

Le bas du menu affiche la version du serveur et le debut du commit actif. La version de cette interface est `atelier-gauche-20261024`. Le diagnostic est disponible sans cle sur `/api/system/version` ; il ne publie aucune configuration privee.

`MAJ_BENDER.ps1` affiche sept etapes : tests locaux, commit et push, preparation, transfert, installation Debian, verification reseau, fin. Tant que les tests ne sont pas termines, aucun code nouveau n'est envoye au Debian. Attendre le message `[7/7] Deploiement termine et version reseau confirmee.` Le script compare le commit attendu avec celui du processus demarre par systemd, puis controle les nouveaux fichiers de l'interface depuis le PC Windows. Une simple reponse HTTP 200 de l'ancienne version ne suffit plus pour annoncer un succes.


Le controle des processus de preparation est portable : Windows utilise un handle de synchronisation et ne recoit aucun signal pour tester l'existence d'un worker. Le processus courant est identifie directement. Sur Linux, la sonde POSIX conserve les erreurs de permission comme un processus encore actif.

Les tests du deploiement passent par `scripts/run-tests.py`. Ce lanceur ecrit un recu seulement apres la reussite et la fin de tous les tests decouverts. PowerShell verifie le nombre execute et l'identifiant unique de cette execution. Un arret silencieux de Python avec un code de sortie nul ne permet plus de continuer vers GitHub et Debian.
