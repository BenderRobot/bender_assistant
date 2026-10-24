import random
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from bender_brain.quick_replies import quick_reply
from bender_voice import waiting
from bender_voice.moods import command as mood_command
from bender_voice.providers import VoiceUnavailable
from hardware_api import require_control
from voice_api import get_voice

router = APIRouter()


class WaitingRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    mode: Literal['auto', 'local', 'cloud', 'cache'] = 'auto'
    previous: str = Field(default='', max_length=64)


@router.get('/api/voice/waiting')
def status(voice=Depends(get_voice)):
    return waiting.catalogue(voice)


@router.post('/api/voice/waiting/prepare', dependencies=[Depends(require_control)])
def prepare(voice=Depends(get_voice)):
    try:
        return waiting.prepare(voice)
    except VoiceUnavailable as error:
        raise HTTPException(503, str(error)) from error


@router.post('/api/chat/acknowledgement', dependencies=[Depends(require_control)])
def acknowledgement(req: WaitingRequest, voice=Depends(get_voice)):
    if req.mode == 'local' or quick_reply(req.message) is not None or mood_command(req.message) is not None or not voice.config.get('elevenlabs', {}).get('enabled'):
        return {'segment': None}
    items = waiting.catalogue(voice)['items']
    choices = [item for item in items if item['id'] != req.previous] or items
    return {'segment': random.choice(choices) if choices else None}
