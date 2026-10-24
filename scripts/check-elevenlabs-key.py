"""Verify credential presence through the runtime loader, without printing it."""
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bender_voice.environment import load_environment

if __name__ == '__main__':
    load_environment()
    if not os.environ.get('ELEVENLABS_API_KEY', '').strip():
        raise SystemExit('Cle ElevenLabs absente ou vide dans cet environnement. Aucun contenu de cle affiche.')
    print('Cle ElevenLabs chargee par le moteur Bender (valeur masquee). Validite distante non testee.')
