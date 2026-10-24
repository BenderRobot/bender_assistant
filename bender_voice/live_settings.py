"""Public voice preferences; API credentials stay in the environment."""
import json
from pathlib import Path
import uuid


def read(root):
    path=Path(root)/'live-settings.json'
    if not path.exists():return {}
    value=json.loads(path.read_text(encoding='utf-8'))
    if set(value)-{'enabled','voice_id','model_id'}:raise ValueError('Réglages de voix invalides')
    if not isinstance(value.get('enabled'),bool):raise ValueError('Activation de voix invalide')
    return value


def save(root,value):
    path=Path(root)/'live-settings.json';temp=path.with_name(uuid.uuid4().hex+'.tmp')
    try:
        temp.write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8');temp.replace(path)
    finally:temp.unlink(missing_ok=True)
