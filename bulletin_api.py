from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from hardware_api import require_control
from voice_api import get_voice
from bender_voice.bulletins import Bulletins
from bender_voice import live_settings

router=APIRouter(dependencies=[Depends(require_control)])


class NewsSettings(BaseModel):
    enabled:bool=False
    time:str=Field(default='06:00',pattern=r'^(?:[01]\d|2[0-3]):[0-5]\d$')
    timezone:Literal['Europe/Paris']='Europe/Paris'
    mood:Literal['neutral','sarcastic','angry','excited','sad']='excited'
    feeds:list[str]=Field(default_factory=list,max_length=6)
    max_items:int=Field(default=8,ge=1,le=8)


class LiveSettings(BaseModel):
    enabled:bool=False
    voice_id:str=Field(default='',max_length=80,pattern=r'^[a-zA-Z0-9_-]*$')
    model_id:Literal['eleven_flash_v2_5','eleven_multilingual_v2','eleven_v3']='eleven_flash_v2_5'


@router.post('/api/voice/live-settings')
def set_live(req:LiveSettings,voice=Depends(get_voice)):
    if req.enabled and not req.voice_id:raise HTTPException(400,'Renseigner le Voice ID ElevenLabs')
    with voice.lock:
        live_settings.save(voice.store.root,req.model_dump())
        voice.config['elevenlabs']={**voice.config.get('elevenlabs',{}),**req.model_dump()}
    return dict(saved=True,note='Réglages enregistrés. La clé API doit être présente sur Debian pour générer la voix.')


@router.get('/api/bulletins')
def state(voice=Depends(get_voice)):
    service=Bulletins(voice)
    return dict(settings=service.settings(),today=service.today())


@router.post('/api/bulletins/settings')
def configure(req:NewsSettings,voice=Depends(get_voice)):
    try:return Bulletins(voice).configure(req.model_dump())
    except (ValueError,OSError) as error:raise HTTPException(400,str(error)) from error


@router.post('/api/bulletins/queue')
def queue(voice=Depends(get_voice)):
    try:return Bulletins(voice).queue()
    except ValueError as error:raise HTTPException(400,str(error)) from error


@router.post('/api/bulletins/play')
def play(voice=Depends(get_voice)):
    try:return Bulletins(voice).playback()
    except ValueError as error:raise HTTPException(409,str(error)) from error
