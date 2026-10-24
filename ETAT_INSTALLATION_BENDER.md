# Installation Bender — contrôle du 24 octobre 2026

Contrôle par HTTP et SSH, sans synthèse vocale, analyse GPT ni modification des samples.

| Élément sur Debian | État observé |
| --- | --- |
| Serveur web | Accessible, `bender.service` actif |
| Version exécutée | `7ea55fc` — Conversation rapide et salutations locales |
| Cerveau GPT | Connecté et autorisé ; modèle principal configuré : `gpt-6.1-sol` |
| ElevenLabs | Activé ; clé chargée, SDK présent, modèle `eleven_flash_v2_5` |
| Chatterbox | Paquet présent ; références actives : neutre et énergique |
| Transcription des samples | `faster-whisper`, medium, français ; modèle local présent |
| Outils matériels | FFmpeg, FFprobe, arecord et aplay présents |
| Traitement des samples | Dernière exécution du service terminée avec succès ; aucune analyse en cours |
| Mémoire disponible | Environ 6 Go au moment du contrôle |
| Disque disponible | Environ 47 Go au moment du contrôle |

La présence des paquets et modèles ne remplace pas un essai réel du son et de la
caméra. Aucun nouvel appel payant ni chargement du modèle Chatterbox n'a été
déclenché pour ce contrôle. Le service de traitement est de type `oneshot` : son
état inactif après une sortie avec succès est normal.

## Bibliothèque existante

- 25 fichiers importés, dont 14 à vérifier et 11 avec des sélections validées.
- 11 sélections de répliques, 5 références vocales et 1 repère d'expression.
- Références actives Chatterbox : neutre et énergique. Les autres références
  restent des candidates validées, à activer explicitement pour leur humeur.
- Aucune sélection validée n'est classée triste.
- 2 transcriptions portent une provenance Whisper ; 23 sont anciennes ou sans
  provenance enregistrée. Ne pas les attribuer automatiquement à Vosk ni écraser
  d'éventuelles corrections manuelles.
- Aucun fichier de référence vocale validée manquant au moment du contrôle.
- Aucun sample en erreur ou en cours d'analyse.

Ces nombres désignent des sélections, pas nécessairement des répliques distinctes :
plusieurs passages d'un même fichier ont pu être validés séparément.

## Poste de développement et déploiement

Le dépôt principal est `Documents/bender_main/bender_assistant`. L'environnement
Python principal Windows est en version 3.12.1 ; le Debian utilise Python 3.11.2.
Le venv Windows principal contient FastAPI et ElevenLabs, mais pas les moteurs
locaux Vosk, Whisper et Chatterbox. Ceux-ci sont installés sur Debian ; cela
n'empêche pas de développer et tester l'atelier sur Windows avec des doublures.

Les phrases d'attente et la nouvelle vue **Versions de Bender** sont des
modifications locales postérieures au commit exécuté sur Debian. Elles devront
passer par la mise à jour habituelle avant d'apparaître sur le robot.

## Suite pour l'étape 03

1. Déployer la vue des versions, puis vérifier les sélections déjà validées.
2. Écouter et corriger les 14 samples encore à vérifier, en privilégiant les
   meilleures répliques et des références propres pour les humeurs manquantes.
3. Valider un usage et une humeur pour chaque passage utile, puis tester les
   répliques avec la bouche depuis la bibliothèque.
4. Vérifier les mots déclencheurs et les réglages contextuels en conversation.
   Le classement par humeur ne choisit pas encore automatiquement l'émotion GPT
   ni le style de la voix ElevenLabs.
