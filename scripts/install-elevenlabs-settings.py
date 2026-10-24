"""Install the voice choice received over SSH; never reads or handles API keys."""
from pathlib import Path
import hashlib
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bulletin_api import LiveSettings
from bender_voice.config import load_config
from bender_voice.live_settings import save


def install(source, config_path=None):
    settings = LiveSettings.model_validate_json(Path(source).read_text(encoding='utf-8-sig'))
    if settings.enabled and not settings.voice_id:
        raise ValueError('Voice ID requis pour activer ElevenLabs')
    root = Path(load_config(config_path)['data_dir'])
    root.mkdir(parents=True, exist_ok=True)
    signature = hashlib.sha256(json.dumps(settings.model_dump(), sort_keys=True).encode()).hexdigest()
    marker = root / 'deployed-live-settings.sha256'
    if marker.exists() and marker.read_text(encoding='utf-8') == signature:
        return False  # Keep choices made later in the Debian workshop.
    save(root, settings.model_dump())
    marker.write_text(signature, encoding='utf-8')
    return True


if __name__ == '__main__':
    changed = install(sys.argv[1])
    print('Choix de voix ElevenLabs installé.' if changed else 'Choix ElevenLabs du Debian conservé.')
