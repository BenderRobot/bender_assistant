"""Load private project settings without depending on the launch directory."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def load_environment(root=ROOT):
    # A blank systemd/legacy .env placeholder is not a usable credential.
    # Keep real process credentials authoritative, but allow the private file
    # to fill a missing or empty key. Voice activation is controlled separately.
    if not os.environ.get('ELEVENLABS_API_KEY', '').strip():
        os.environ.pop('ELEVENLABS_API_KEY', None)
    root = Path(root)
    load_dotenv(root / ".env.elevenlabs", override=False, encoding='utf-8-sig')
    if not os.environ.get('ELEVENLABS_API_KEY', '').strip():
        os.environ.pop('ELEVENLABS_API_KEY', None)
    load_dotenv(root / ".env", override=False, encoding='utf-8-sig')
