# Bender : voix hybrides et visage

**Version micro/caméra/son du Dell :** voir [MISE_A_JOUR_DEBIAN.md](MISE_A_JOUR_DEBIAN.md) pour les boutons de capture, Vosk local, la clé de contrôle et la lecture sur les enceintes du Dell.

Version locale pour tester le texte → audio → bouche sur Debian. Quatre niveaux partagent le même lecteur :

1. Réponses enregistrées et cache : aucune génération supplémentaire.
2. Chatterbox Multilingual, local, pour préparer les textes et bulletins à l'avance avec une référence française choisie par humeur.
3. ElevenLabs, après activation, pour les nouvelles réponses de conversation. Aucun repli automatique vers une génération Chatterbox lente.
4. Bibliothèque de répliques contextuelles, jouées après la réponse avec probabilité et délais anti-répétition.

Le texte généré par GPT passe dans cette chaîne. Le test voix seul fonctionne sans connexion au cerveau. Voir [CERVEAU_GPT.md](CERVEAU_GPT.md) pour connecter le compte ChatGPT depuis Windows. L'interface affiche les sources réellement utilisées et les replis. Les fenêtres yeux et bouche suivent le même audio via WebSocket, à 20 mises à jour par seconde.

Le parcours **conversation API + bulletin RSS préparé à 6 h, lu à la demande** est décrit dans [VOIX_CONVERSATION_ET_BULLETINS.md](VOIX_CONVERSATION_ET_BULLETINS.md).

## Installation Debian

Extraire l'archive du projet dans un dossier personnel, puis :

```bash
bash scripts/install-debian.sh --system-deps
export BENDER_VOICE_CONFIG=voice.json
.venv/bin/python server.py
```

Ouvrir **http://127.0.0.1:8000** sur le Dell. Commencer par « Faire parler » ; le bouton GPT nécessite la connexion du compte ChatGPT et la clé de contrôle du Dell. Voir [CERVEAU_GPT.md](CERVEAU_GPT.md). Le moteur système `espeak-ng` permet un premier essai sans modèles ni compte, avec une voix générique clairement indiquée. Pour utiliser directement les enregistrements, choisir le mode « Enregistrements uniquement » après import.

Python 3.11/3.12 est conseillé pour les modèles. `PYTHON_BIN=python3.11 bash scripts/install-debian.sh ...` permet de choisir l'interpréteur installé. Ne pas modifier le Python système. PyAudio est facultatif pour le mode micro historique ; le banc web fonctionne sans microphone.

Le serveur écoute uniquement l'ordinateur local par défaut. `BENDER_HOST=0.0.0.0` dans `.env` permet un essai sur un réseau privé de confiance ; l'interface n'a pas d'authentification. Lancer un seul processus/worker pour partager le lecteur et le chargement des modèles.

## Chatterbox hors ligne

Pour récupérer une voix que tu as créée chez ElevenLabs, suivre [ELEVENLABS_CHATTERBOX.md](ELEVENLABS_CHATTERBOX.md) et les tâches dédiées de l’étape 03 de la roadmap. Générer puis télécharger un WAV, l’importer comme référence vocale, puis utiliser le bouton **Utiliser cette voix avec Chatterbox** dans l’atelier. Le choix persiste dans `data/voice/reference-settings.json`, sans modifier `voice.json` ni activer les appels cloud.

```bash
.venv/bin/python -m pip install -r requirements-chatterbox.txt
.venv/bin/python -m bender_voice --config voice.json download-models chatterbox
```

Ces deux commandes nécessitent Internet. Elles peuvent télécharger plusieurs Go avec les dépendances. La génération utilise ensuite `from_local`, sans téléchargement implicite.

Placer une référence propre en français dans `data/voice/references/neutre.wav`. Configurer `reference_by_mood` dans `voice.json` :

```json
{"neutral":"references/neutre.wav","sarcastic":"references/sarcastique.wav","excited":"references/energique.wav"}
```

Ce sont des références de conditionnement, pas un entraînement cumulatif du modèle. Garder la même identité vocale. Sans référence d'humeur, la référence neutre est utilisée. Tester le résultat et la latence sur le Dell ; le CPU est accepté, la rapidité n'est pas garantie. Pour une carte NVIDIA compatible et PyTorch CUDA installé, choisir `chatterbox.device` = `cuda`. `system_fallback=false` interdit le repli sur la voix générique.

## ElevenLabs et maîtrise du budget

Le SDK Python officiel `elevenlabs` est installé avec les dépendances. La connexion par le CLI est décrite dans [ELEVENLABS_INTEGRATION.md](ELEVENLABS_INTEGRATION.md). Le serveur et la commande vocale chargent `.env.elevenlabs`, puis `.env`, depuis le dossier du projet ; les variables déjà définies dans le processus restent prioritaires. Aucun fichier de clé n'est publié sur GitHub.

Dans **Voix et enregistrements**, renseigner le Voice ID de ta voix, choisir le modèle et activer ElevenLabs. Le mode automatique réutilise d'abord les enregistrements et le cache, puis ElevenLabs pour les nouvelles réponses. Chatterbox reste réservé aux préparations ou au mode local explicite. Le mode local ne contacte jamais ElevenLabs.

Les plafonds `daily_character_limit` et `monthly_character_limit` comptent les caractères réservés par jour et mois civil UTC, tous appels de ce service confondus. Le mois civil ne coïncide pas nécessairement avec le cycle de facturation. Ce n'est pas le solde exact des crédits ElevenLabs, dont le coût dépend du modèle. Une réservation reste comptée si un appel échoue : le service distant a pu générer/facturer malgré une coupure. Les nouvelles tentatives du SDK sont désactivées. En conversation, une erreur ou un plafond atteint utilise la voix système si elle est autorisée, sans lancer Chatterbox.

Le cache inclut le texte, la source de voix, la référence Chatterbox, l'humeur et les réglages. Les futures répétitions réutilisent audio et timeline. Pour remplacer une voix après changement de poids de modèle, augmenter `cache_version` dans `voice.json`. Le mode local permet de générer une première version locale même si une version cloud existe en cache. Un ancien repli système peut être repris en mode auto : choisir local pour régénérer avec Chatterbox après son installation.

## Importer tes samples

Garder les fichiers source hors du dépôt. Le programme les convertit en WAV PCM16 mono :

```bash
.venv/bin/python -m bender_voice --config voice.json import /chemin/ma-replique.mp3 \
  --id replique-argent --text "Texte exact de la réplique" \
  --trigger argent --trigger prix --trigger budget
```

Pour une confirmation réutilisable :

```bash
.venv/bin/python -m bender_voice --config voice.json import /chemin/lumiere.wav \
  --id confirmation-lumiere --type basic --text "OK, j'allume la lumière."
```

Une réponse basique remplace uniquement le même texte normalisé, jamais une commande utilisateur avant son exécution. Une erreur d'allumage ne doit pas rejouer une confirmation de succès. Le Home Assistant de ce dépôt est encore un stub : les vraies commandes domotiques restent à implémenter.

Le catalogue est dans `data/voice/library/catalog.json`. Voir `library.example.json`. Chaque réplique a ses mots déclencheurs, humeurs facultatives, expression des yeux facultative et délai. Les déclencheurs sont comparés par mots entiers, sans reconnaissance sémantique LLM. `quotes.probability` règle la fréquence (0 à 1) et `global_cooldown_seconds` le délai entre deux interventions. L'interface doit autoriser les répliques ; elles ne sont jamais imposées à chaque réponse.

Ajouter `--timeline /chemin/calage.json` pour reprendre des poses manuelles, ou `--eyes ref3` pour enregistrer explicitement une expression. Sans cela les yeux restent indépendants. Le JSON accepte `cues` avec `t` en secondes, `pose` de 0 à 11 et `rounded` facultatif. La durée est validée contre l'audio.

## Synchronisation labiale et écrans

Les douze poses du banc sont reprises : petite/grande pose 3, extrémités légèrement ouvertes pour le cri, coins resserrés et ouverture centrale, dents arrondies, ouverture avec rangées supérieures fixes. La table `bender_voice/visemes-fr.json` reste un routage stylisé à valider.

Par défaut, la timeline vient du volume de l'audio : c'est une estimation acoustique explicitement indiquée. Pour activer le prototype phonétique :

```bash
.venv/bin/python -m pip install -r requirements-phonemes.txt
.venv/bin/python -m bender_voice --config voice.json download-models allosaurus
```

Choisir ensuite `lipsync.engine` = `allosaurus` dans `voice.json`. Ses sons et horaires sont approximatifs ; les trous utilisent un secours acoustique signalé. Le cri prolongé était mal reconnu lors de nos essais. Aucun entraînement du modèle sur les vidéos n'est effectué. Les horaires de caractères ElevenLabs sont conservés dans les métadonnées ; ils ne sont pas présentés comme des phonèmes.

Sur le navigateur du Dell :

- `/` : contrôleur, audio et banc.
- `/face?display=eyes` : écran LCD, canevas 800 × 480.
- `/face?display=mouth` : bouche, canevas 128 × 64, pixels nets.

Double-cliquer sur une fenêtre d'affichage pour le plein écran. L'audio sort du Dell si la sortie hôte est choisie, ou du navigateur en mode banc. Les fenêtres suivent les poses via `/api/face`, puis reviennent au repos si le contrôleur disparaît. Les noms et positions des yeux sont réutilisés, sans liaison automatique à une bouche.

**Matériel HUB75/MatrixPortal S3 :** cette version fournit les poses et leur horloge, mais pas encore le firmware ou le transport USB/série de la matrice physique. Le rendu HDMI/navigateur est testable ; le pilote du panneau devra consommer ces événements. Le mode CLI `say --play` et les minuteurs lisent l'audio sur l'hôte via ffplay ; la diffusion du visage est assurée par le lecteur web ou par le nouveau lecteur ALSA du serveur.

Le cerveau GPT nécessite Internet et un compte ChatGPT autorisé ; le micro du banc web utilise Vosk localement. La reconnaissance micro Google du vieux mode terminal nécessite aussi Internet. Seules la synthèse locale, la bibliothèque, les timelines locales et leur lecture peuvent fonctionner hors ligne.

## Tests et API d'intégration

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m unittest discover -s tests -v
```

Les tests simulent les synthèses distantes : aucune dépense ni clé nécessaire. Ils couvrent cache, budget persistant, appels concurrents, repli, imports, correspondance exacte des confirmations, répliques, timelines, API et WebSocket.

`POST /api/speech` reçoit `{ "text":"Bonjour", "mode":"auto", "mood":"neutral", "context":"salon", "topic":"", "allow_quote":true }`. La réponse contient `segments`, chacun avec `audio_url`, `timeline_url`, `source`, `cached`, `duration`, `warnings`. Jouer les segments dans l'ordre. `GET /api/voice/status` donne l'état et le compteur ; `POST /api/chat` conserve le champ `response` et ajoute `speech` quand disponible.

`python -m bender_voice --config voice.json say "Bonjour" --mode local --play` teste la voix depuis le terminal. `status` affiche le compteur. Le fichier `deploy/bender.service.example` est un modèle systemd à adapter, sans installation automatique.

## État de cette livraison

Routage/API, bibliothèque, budget et diffusion des poses testés avec des moteurs simulés et un WAV réel. Génération réelle Chatterbox/ElevenLabs non validée ici : il manque la référence finale, le modèle sur Debian et les identifiants ElevenLabs. La vitesse GPU/CPU et le son du Dell demandent un test sur place. Aucun appel GPT, ElevenLabs ou domotique n'est effectué pendant les tests. La connexion ChatGPT réelle doit être validée sur Debian après autorisation personnelle.

L'ancien dépôt suit déjà un `.env`, un exemple contenant une clé et une base de mémoire. L'exemple a été nettoyé ; révoquer la clé déjà exposée et retirer les secrets de l'historique Git séparément. L'archive de livraison exclut `.env`, la mémoire, les médias, les modèles et les caches.

Références : [Chatterbox](https://github.com/resemble-ai/chatterbox), [ElevenLabs audio avec horaires](https://elevenlabs.io/docs/api-reference/text-to-speech/convert-with-timestamps), [Allosaurus](https://github.com/xinjli/allosaurus).

## Étape 03 : samples et personnalité

Déposer les nouveautés dans `../02_VOIX_ET_ANIMATIONS/a_importer`, puis lancer la mise à jour habituelle. Les samples sont transcrits hors ligne avec Whisper medium français (modèle ~1,5 Go installé une seule fois), puis classés par GPT. Le menu **Samples et personnalité** affiche leur progression, permet de retranscrire les anciens résultats Vosk et de valider les passages. Guide : [SAMPLES_PERSONNALITE.md](SAMPLES_PERSONNALITE.md).
