import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_config(path=None):
    path = Path(path or os.getenv('BENDER_VOICE_CONFIG', ROOT / 'voice.example.json')).resolve()
    config = json.loads(path.read_text(encoding='utf-8-sig'))
    config['_base'] = str(path.parent)
    config['data_dir'] = str((path.parent / config.get('data_dir', 'data/voice')).resolve())
    if config.get('local_provider', 'chatterbox') not in ('chatterbox', 'system'):
        raise ValueError('local_provider doit être chatterbox ou system')
    for field, default in [('daily_character_limit', 2000), ('monthly_character_limit', 25000)]:
        limit = config.get('elevenlabs', {}).get(field, default)
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 0:
            raise ValueError(field + ' doit être un entier positif ou nul')
    return config


def inside(root, relative):
    root = Path(root).resolve()
    target = (root / relative).resolve()
    if not target.is_relative_to(root):
        raise ValueError('Chemin hors du répertoire autorisé')
    return target
