import asyncio
from functools import lru_cache
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from bender_voice.config import load_config
from bender_voice.hardware import Hardware, HardwareError, HardwareBusy
from bender_voice.host_player import HostPlayer
from voice_api import get_voice, broadcast_face, set_host_face_active


@lru_cache(maxsize=1)
def get_hardware():
    return Hardware(load_config())


@lru_cache(maxsize=1)
def _player_for(voice, hardware):
    return HostPlayer(voice, hardware, broadcast_face, set_host_face_active)


def get_host_player(voice=Depends(get_voice), hardware=Depends(get_hardware)):
    return _player_for(voice, hardware)


def require_control(key: str = Header(default='', alias='X-Bender-Control-Token'), hardware=Depends(get_hardware)):
    if not hardware.authorized(key):
        raise HTTPException(403, 'Clé de contrôle requise ; obtenir la clé avec la commande control-token sur Debian')


class ListenRequest(BaseModel):
    seconds: int = Field(default=6, ge=2, le=15)


class PlaybackRequest(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=16)
    eyes: Literal['normal', 'angry', 'happy', 'surprised', 'sleepy', 'sad', 'worried', 'crying', 'ref1', 'ref2', 'ref3', 'ref4', 'ref5'] = 'normal'


class VisionRequest(BaseModel):
    photo_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    question: str = Field(default='Décris ce que tu vois devant toi.', min_length=1, max_length=2000)
    mode: Literal['auto', 'local', 'cloud', 'cache'] = 'auto'
    mood: str = Field(default='neutral', max_length=40)


def device_error(exc):
    return HTTPException(409 if isinstance(exc, HardwareBusy) else 503, str(exc))


def build_hardware_router(brain_callback):
    router = APIRouter()

    @router.get('/api/hardware/status')
    def status(hardware=Depends(get_hardware)):
        return hardware.status()

    @router.post('/api/hardware/listen', dependencies=[Depends(require_control)])
    async def listen(req: ListenRequest, hardware=Depends(get_hardware), player=Depends(get_host_player)):
        await player.stop()  # Éviter que Bender transcrive sa propre voix.
        try:
            return await asyncio.to_thread(hardware.listen, req.seconds)
        except HardwareError as exc:
            raise device_error(exc) from exc

    @router.post('/api/hardware/camera', dependencies=[Depends(require_control)])
    async def camera(hardware=Depends(get_hardware)):
        try:
            return await asyncio.to_thread(hardware.capture)
        except HardwareError as exc:
            raise device_error(exc) from exc

    @router.get('/api/hardware/photos/{identifier}', dependencies=[Depends(require_control)])
    def photo(identifier: str, hardware=Depends(get_hardware)):
        try:
            path = hardware.photo_path(identifier)
        except ValueError as exc:
            raise HTTPException(404, 'Photo introuvable') from exc
        if not path.is_file():
            raise HTTPException(404, 'Photo introuvable')
        return FileResponse(path, media_type='image/jpeg', headers={'Cache-Control': 'no-store'})

    @router.post('/api/hardware/vision', dependencies=[Depends(require_control)])
    async def vision(req: VisionRequest, hardware=Depends(get_hardware), voice=Depends(get_voice)):
        path = hardware.photo_path(req.photo_id)
        if not path.is_file():
            raise HTTPException(404, 'Photo expirée ; reprendre une capture')
        image = path.read_bytes()
        if len(image) > 4_000_000:
            raise HTTPException(400, 'Photo trop volumineuse')
        try:
            response = await asyncio.to_thread(brain_callback, req.question, image)
        except Exception as exc:
            raise HTTPException(503, 'Vision Gemini indisponible ; vérifier GEMINI_API_KEY et Internet') from exc
        result = {'response': response}
        try:
            result['speech'] = await asyncio.to_thread(voice.prepare, response, req.mode, req.mood)
        except Exception:
            result['speech_error'] = 'Réponse reçue, mais synthèse vocale indisponible'
        return result

    @router.post('/api/hardware/play', dependencies=[Depends(require_control)])
    async def play(req: PlaybackRequest, player=Depends(get_host_player)):
        try:
            return await player.start(req.ids, req.eyes)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except HardwareError as exc:
            raise device_error(exc) from exc

    @router.post('/api/hardware/stop', dependencies=[Depends(require_control)])
    async def stop(player=Depends(get_host_player)):
        return await player.stop()

    @router.get('/api/hardware/playback', dependencies=[Depends(require_control)])
    def playback(player=Depends(get_host_player)):
        return player.state

    return router
