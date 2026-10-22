# Mise à jour micro, caméra et son du Dell

Cette archive remplace le code dans `bender_assistant`. Elle ne contient pas `.env`, `voice.json`, les médias, bases mémoire, clés ou modèles et conserve donc ces éléments existants.

## Transfert

Télécharger `Bender_Debian_micro_camera_v2.zip` dans les Téléchargements Windows, puis lancer dans PowerShell :

```powershell
scp -F NUL "$env:USERPROFILE\Downloads\Bender_Debian_micro_camera_v2.zip" bender@192.168.1.41:~/
```

Dans le terminal Debian du serveur, faire **Ctrl+C**, puis :

```bash
unzip -o ~/Bender_Debian_micro_camera_v2.zip -d ~/applications
cd ~/applications/bender_assistant
sudo apt install -y alsa-utils ffmpeg v4l-utils
.venv/bin/python -m pip install -r requirements-io.txt
.venv/bin/python -m bender_voice --config voice.json download-models vosk
.venv/bin/python -m bender_voice --config voice.json control-token
```

La dernière commande affiche ta clé de contrôle. La copier pour la coller dans la page, sans la publier dans le chat. Elle est distincte de tes clés Gemini et ElevenLabs.

Relancer :

```bash
BENDER_HOST=0.0.0.0 BENDER_VOICE_CONFIG=voice.json .venv/bin/python server.py
```

Ouvrir **http://192.168.1.41:8000**, faire **Ctrl+F5**, coller la clé dans « Clé de contrôle du Dell ».

## Essais

1. **Caméra** : « Prendre une photo · LifeCam ». L'image doit apparaître sur la page.
2. **Micro** : décocher « Envoyer la transcription au cerveau Gemini et répondre », puis cliquer « Parler à Bender ». Parler pendant la durée choisie. Le texte reconnu s'affiche. Le petit modèle Vosk fonctionne en local et peut se tromper : vérifier le résultat.
3. **Son** : choisir « Enceintes du Dell », taper une phrase et cliquer « Faire parler ». Le son doit sortir du Dell et la bouche suivre. Tant que les voix personnalisées ne sont pas configurées, le repli système utilise une voix générique.
4. **Chaîne complète** : renseigner `GEMINI_API_KEY` dans `.env`, redémarrer, puis recocher l'envoi au cerveau. « Analyser la photo avec Gemini » utilise aussi cette clé et Internet. Une simple capture n'envoie aucune photo au modèle.

## Réglages et fonctionnement

Les anciens `voice.json` sont compatibles. Sans bloc `hardware`, les valeurs par défaut correspondent au matériel testé :

```json
{
  "hardware": {
    "input_device": "plughw:CARD=HD3000,DEV=0",
    "output_device": "plughw:CARD=PCH,DEV=0",
    "camera_device": "/dev/video0",
    "vosk_model_dir": "models/vosk-fr"
  }
}
```

Le micro enregistre sur demande, pendant 6, 10 ou 15 secondes, en mono PCM16 16 kHz. Le fichier temporaire est supprimé après transcription. Il n'y a pas encore d'écoute permanente ou de mot d'activation.

La caméra fournit une photo MJPEG 640 × 480. Seules les trois dernières captures sont conservées. Leur lecture exige la clé de contrôle.

La lecture hôte utilise `aplay` et la sortie PCH. Le serveur diffuse les poses de bouche à 25 Hz pendant le son. Sa bouche suit une horloge estimée depuis le lancement d'ALSA, sans mesure exacte de latence du haut-parleur. La lecture est arrêtée avant la capture micro pour éviter que Bender ne se transcrive lui-même. Le choix « Ce navigateur » conserve l'ancien banc et ses vitesses de comparaison.

Les fenêtres `/face?display=eyes` et `/face?display=mouth` suivent aussi la lecture sur le Dell. Le pilote physique HUB75 reste à ajouter. Le mode CLI historique et les minuteurs utilisent toujours leur ancien lecteur sans cette diffusion de visage.

La clé de contrôle est conservée dans `data/voice/hardware/control-token` (droits 600 sous Debian), et dans la session du navigateur après saisie. Elle n'est jamais placée dans une URL. `BENDER_CONTROL_TOKEN`, au moins 20 caractères, peut remplacer ce fichier. Les nouveaux accès matériels sont protégés ; le reste de l'ancienne interface n'a pas encore d'authentification globale. Garder le serveur sur un réseau privé.

API : `GET /api/hardware/status` ; `POST /api/hardware/listen` (`seconds`) ; `POST /api/hardware/camera` ; `GET /api/hardware/photos/{id}` ; `POST /api/hardware/vision` (`photo_id`, `question`, `mode`, `mood`) ; `POST /api/hardware/play` (`ids`, `eyes`) ; `POST /api/hardware/stop`. Toutes sauf l'état demandent l'en-tête `X-Bender-Control-Token`.

## Validation

22 tests automatisés passent, dont l'accès matériel, la conversion, les verrous de capture, le lecteur ALSA simulé et la remise au repos des poses. Vosk et son modèle français ont été réellement exécutés sur un WAV fourni. Les périphériques physiques intégrés n'ont pas été testés à distance : ils sont à confirmer sur le Dell. Aucune requête Gemini ou ElevenLabs n'a été exécutée pendant les tests.
