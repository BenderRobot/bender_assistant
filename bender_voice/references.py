"""Persistent local voice references, independent from deployed configuration."""
import json
from pathlib import Path
import uuid

from .config import inside

MOODS=('neutral','sarcastic','angry','excited','sad')


def validate(root,references):
    if not isinstance(references,dict) or set(references)-set(MOODS):
        raise ValueError('Humeurs de référence vocale invalides.')
    directory=inside(root,'references')
    for name in references.values():
        if not isinstance(name,str) or not inside(root,name).is_relative_to(directory) or Path(name).suffix.lower()!='.wav':
            raise ValueError('Choisir une référence WAV dans le dossier references.')
    return references


def read(root):
    path=Path(root)/'reference-settings.json'
    if not path.exists():return {}
    try:
        value=json.loads(path.read_text(encoding='utf-8'))
        if value.get('version')!=1:raise ValueError('Version inconnue')
        return validate(root,value['reference_by_mood'])
    except (OSError,KeyError,TypeError,AttributeError,ValueError) as exc:
        raise ValueError('Références locales invalides dans reference-settings.json.') from exc


def save(root,references):
    validate(root,references)
    path=Path(root)/'reference-settings.json'
    temporary=path.with_name('reference-settings-'+uuid.uuid4().hex+'.tmp')
    try:
        temporary.write_text(json.dumps(dict(version=1,reference_by_mood=references),ensure_ascii=False,indent=2),encoding='utf-8')
        temporary.replace(path)
    finally:temporary.unlink(missing_ok=True)
