#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
system_deps=false
chatterbox=false
phonemes=false
micro=false
samples=false
for argument in "$@"; do
  case "$argument" in
    --system-deps) system_deps=true ;;
    --chatterbox) chatterbox=true ;;
    --phonemes) phonemes=true ;;
    --micro) micro=true ;;
    --samples) samples=true ;;
    *) echo "Usage: $0 [--system-deps] [--chatterbox] [--phonemes] [--micro] [--samples]"; exit 2 ;;
  esac
done
if "$system_deps"; then
  sudo apt-get update
  sudo apt-get install -y python3 python3-venv python3-dev ffmpeg espeak-ng alsa-utils v4l-utils libsndfile1 portaudio19-dev build-essential
fi
python_bin="${PYTHON_BIN:-python3}"
"$python_bin" -c 'import sys; assert (3,10) <= sys.version_info[:2] <= (3,13), "Python 3.10 à 3.13 requis ; 3.11 ou 3.12 conseillé pour les modèles vocaux"'
"$python_bin" -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
if "$chatterbox"; then .venv/bin/python -m pip install -r requirements-chatterbox.txt; fi
if "$phonemes"; then .venv/bin/python -m pip install -r requirements-phonemes.txt; fi
if "$micro"; then .venv/bin/python -m pip install -r requirements-io.txt; fi
if "$samples"; then .venv/bin/python -m pip install -r requirements-samples.txt; fi
if [[ ! -f .env ]]; then cp .env.example .env; fi
if [[ ! -f voice.json ]]; then cp voice.example.json voice.json; fi
mkdir -p data/voice/references data/voice/library
if "$samples"; then .venv/bin/python -m bender_voice --config voice.json download-models whisper; fi
echo "Installation terminée. Lancement : BENDER_VOICE_CONFIG=voice.json .venv/bin/python server.py"
echo "Chatterbox/Allosaurus : télécharger les modèles séparément, voir README.md."
