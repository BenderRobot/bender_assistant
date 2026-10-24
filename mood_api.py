import asyncio
from functools import lru_cache
import time
from typing import Literal

from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from bender_voice.config import load_config
from bender_voice.moods import MoodScenarios,Scenario,ScenarioConflict,Mood,LABELS,reply
from bender_voice.providers import VoiceUnavailable
from hardware_api import require_control
from voice_api import get_voice


@lru_cache(maxsize=1)
def get_moods():return MoodScenarios(load_config()['data_dir'])


class SaveScenario(BaseModel):
    revision:int=Field(ge=1)
    scenario:Scenario
    duplicate:bool=Field(default=False,alias='copy')


class MoodRequest(BaseModel):
    mood:Mood
    intensity:int=Field(default=2,ge=1,le=3)
    mode:Literal['auto','local','cloud','cache']='auto'
    speech:bool=True


router=APIRouter(prefix='/api/moods',dependencies=[Depends(require_control)])


@router.get('')
def catalog(store=Depends(get_moods)):
    return {**store.catalog(),'moods':LABELS}


@router.post('')
def save(req:SaveScenario,store=Depends(get_moods)):
    try:return store.save(req.scenario,req.revision,req.duplicate)
    except ScenarioConflict as exc:raise HTTPException(409,str(exc)) from exc
    except ValueError as exc:raise HTTPException(400,str(exc)) from exc


@router.post('/prepare')
async def prepare(req:MoodRequest,store=Depends(get_moods),voice=Depends(get_voice)):
    started=time.perf_counter()
    try:
        result=await asyncio.to_thread(reply,store,voice,req.mood,req.intensity,req.mode,req.speech)
        if req.speech:result['timings']['voice_seconds']=round(time.perf_counter()-started,3)
        return result
    except (ValueError,VoiceUnavailable,OSError) as exc:raise HTTPException(400,str(exc)) from exc
