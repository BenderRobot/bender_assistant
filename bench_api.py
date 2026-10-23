"""Reference recordings and explicit library playback for the workshop UI."""
import hashlib
import json
import os
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Literal

from voice_api import get_voice
from bender_voice.config import inside
from bender_voice.lipsync import LipSync, read_wav, validate_timeline

ROOT = Path(__file__).resolve().parent


class ReferenceRequest(BaseModel):
    method: Literal['visual', 'phonemes', 'acoustic'] = 'acoustic'


def build_bench_router(directory=None):
    router = APIRouter(prefix='/api/bench')
    root = Path(directory or os.getenv('BENDER_REFERENCE_DIR', ROOT / 'data' / 'reference_samples'))

    def catalog():
        path = root / 'catalog.json'
        return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else []

    @router.get('/recordings')
    def recordings(service=Depends(get_voice)):
        references = [{key: entry[key] for key in ('id', 'title', 'duration')} | {'methods': list(entry.get('methods', {})) + ['acoustic']}
                      for entry in catalog() if inside(root, entry['audio']).is_file()]
        library = [{'id': entry['id'], 'title': entry.get('text') or entry['id'], 'type': entry.get('type', 'quote')}
                   for entry in service.store.library() if entry.get('enabled', True)]
        return {'references': references, 'library': library}

    @router.post('/references/{identifier}/prepare')
    def prepare(identifier: str, req: ReferenceRequest, service=Depends(get_voice)):
        entry = next((item for item in catalog() if item['id'] == identifier), None)
        if not entry:
            raise HTTPException(404, 'Extrait de référence introuvable.')
        try:
            audio = inside(root, entry['audio'])
            samples, rate = read_wav(audio)
            duration = len(samples) / rate
            if req.method == 'acoustic':
                timeline = LipSync({**service.config, 'lipsync': {'engine': 'acoustic'}}).build(audio)
            else:
                name = entry.get('methods', {}).get(req.method)
                if not name: raise ValueError('Ce calage n’est pas disponible pour cet extrait.')
                timeline = validate_timeline(json.loads(inside(root, name).read_text(encoding='utf-8')), duration)
            timeline = {**timeline, 'duration': duration, 'text': entry['title'], 'eyes': 'normal'}
            key = hashlib.sha256(audio.read_bytes() + json.dumps(timeline, sort_keys=True).encode()).hexdigest()
            with service.lock:
                shutil.copy2(audio, service.asset(key, 'wav'))
                service.asset(key, 'json').write_text(json.dumps(timeline, ensure_ascii=False), encoding='utf-8')
                segment = service._segment(key, 'reference', cached=True)
            return {'segments': [segment], 'warnings': []}
        except (ValueError, OSError) as exc:
            raise HTTPException(400, 'Extrait ou calage indisponible : ' + str(exc)) from exc

    @router.post('/library/{identifier}/prepare')
    def library(identifier: str, service=Depends(get_voice)):
        entry = next((item for item in service.store.library() if item['id'] == identifier and item.get('enabled', True)), None)
        if not entry: raise HTTPException(404, 'Enregistrement introuvable dans la bibliothèque.')
        try:
            with service.lock: segment = service._library_segment(entry)
            return {'segments': [segment], 'warnings': []}
        except (ValueError, OSError, RuntimeError) as exc:
            raise HTTPException(400, 'Lecture de bibliothèque indisponible.') from exc

    return router
