import asyncio
import importlib.util
from functools import lru_cache
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from bender_voice.config import load_config
from bender_voice.providers import VoiceUnavailable
from bender_voice.service import VoiceService
from pose_models import MouthShape, EyesShape

router = APIRouter()


@lru_cache(maxsize=1)
def get_voice():
    return VoiceService(load_config())


class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=8000)
    mode: Literal['auto', 'local', 'cloud', 'cache'] = 'auto'
    mood: str = Field(default='neutral', max_length=40)
    context: str = Field(default='', max_length=8000)
    topic: Literal['', 'news', 'narration'] = ''
    allow_quote: bool = False


@router.post('/api/speech')
async def speech(req: SpeechRequest, service=Depends(get_voice)):
    try:
        return await asyncio.to_thread(service.prepare, **req.model_dump())
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except VoiceUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc


@router.get('/api/voice/status')
def status(service=Depends(get_voice)):
    return {'cloud_enabled': service.config.get('elevenlabs', {}).get('enabled', False),
            'local_provider': service.config.get('local_provider', 'chatterbox'),
            'chatterbox_installed': importlib.util.find_spec('chatterbox') is not None,
            'lipsync_engine': service.config.get('lipsync', {}).get('engine', 'acoustic'),
            'library_entries': len(service.store.library()), 'usage': service.store.usage()}


@router.get('/api/voice/assets/{identifier}.{extension}')
def asset(identifier: str, extension: str, service=Depends(get_voice)):
    try:
        path = service.asset(identifier, extension)
    except ValueError as exc:
        raise HTTPException(404, 'Audio introuvable') from exc
    if not path.is_file():
        raise HTTPException(404, 'Audio introuvable')
    return FileResponse(path, media_type='audio/wav' if extension == 'wav' else 'application/json')


class FaceState(BaseModel):
    pose: int = Field(ge=0, le=11)
    eyes: Literal['normal', 'angry', 'happy', 'surprised', 'sleepy', 'sad', 'worried', 'crying', 'ref1', 'ref2', 'ref3', 'ref4', 'ref5'] = 'normal'
    active: bool = False
    rounded: bool = False
    mode: Literal['idle', 'listening', 'thinking', 'alert'] = 'idle'
    blink: bool = False
    custom_mouth: MouthShape | None = None
    custom_eyes: EyesShape | None = None


viewers = set()
host_face_active = False


def set_host_face_active(value):
    global host_face_active
    host_face_active = value


async def broadcast_face(state):
    for viewer in tuple(viewers):
        try:
            await viewer.send_json(state)
        except (RuntimeError, WebSocketDisconnect):
            viewers.discard(viewer)


@router.websocket('/api/face')
async def face_socket(socket: WebSocket):
    from urllib.parse import urlparse
    origin = socket.headers.get('origin')
    if origin and urlparse(origin).netloc != socket.headers.get('host'):
        await socket.close(code=1008)
        return
    await socket.accept()
    viewers.add(socket)
    try:
        while True:
            raw = await socket.receive_json()
            if host_face_active:
                continue
            try:
                state = FaceState.model_validate(raw).model_dump()
            except ValueError:
                continue
            await broadcast_face(state)
    except (WebSocketDisconnect, ValueError):
        pass
    finally:
        viewers.discard(socket)
