import asyncio
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import shutil
import threading
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from bender_media.catalog import Catalog, valid_id
from bender_media.processing import cut_audio
from bender_media.worker import Worker
from bender_media.versions import overview, audio_path
from bender_voice.config import load_config
from bender_voice.providers import VoiceUnavailable
from hardware_api import get_hardware, require_control
from brain_api import get_brain
from voice_api import get_voice

_review_lock=threading.Lock()


@lru_cache(maxsize=1)
def get_media():return Catalog(Path(load_config()['data_dir'])/'media')


@lru_cache(maxsize=1)
def get_media_worker():
    from bender_voice.hardware import Hardware
    return Worker(get_media(),Hardware(load_config()),get_brain())


class MediaOptions(BaseModel):
    automatic:bool


class ReferenceSelection(BaseModel):
    selection_id:str=Field(pattern=r'^[a-f0-9]{16}$')


class Retry(BaseModel):
    transcript:str|None=Field(default=None,max_length=8000)
    retranscribe:bool=False


def queue_transcription(catalog,item):
    media={**item['media']}
    if media.get('transcript'):
        media['previous_transcription']=dict(text=media['transcript'],words=media.get('words',[]),
                                             source=media.get('transcription',{'engine':'vosk-legacy'}))
    media.update(transcribed=False,words=[])
    catalog.update(item['id'],state='pending',error='',progress={},media=media)


class Approval(BaseModel):
    use:Literal['quote','voice_reference','expression']
    start:float=Field(ge=0,le=180)
    end:float=Field(gt=0,le=180)
    text:str=Field(default='',max_length=1000)
    title:str=Field(min_length=1,max_length=120)
    mood:Literal['neutral','sarcastic','angry','excited','sad']='neutral'
    triggers:list[str]=Field(default_factory=list,max_length=12)
    bender_only:bool=False


def approve(catalog,identifier,req,voice):
    with _review_lock:
        item=catalog.get(identifier);media=item['media']
        if item['state'] not in ('review','approved'):raise ValueError('Analyser le sample avant sa validation.')
        if not req.start<req.end<=media.get('duration',0) or req.end-req.start>30:raise ValueError('Choisir un passage de 30 secondes maximum, à l’intérieur du sample.')
        if req.use in ('quote','voice_reference') and not req.bender_only:raise ValueError('Vérifier que seul Bender parle dans le passage choisi avant de le valider.')
        if req.use=='quote' and not req.text.strip():raise ValueError('Vérifier et renseigner le texte exact de la réplique.')
        if req.use=='voice_reference' and req.end-req.start<3:raise ValueError('Choisir au moins trois secondes pour une référence vocale.')
        if req.use=='expression' and not any(req.start<=frame['time']<=req.end for frame in media.get('frames',[])):
            raise ValueError('Choisir un passage contenant une image de référence pour la bouche et les yeux.')
        if any(not trigger.strip() or len(trigger)>120 for trigger in req.triggers):raise ValueError('Mots déclencheurs invalides.')
        # Stable approval IDs make repeated clicks idempotent, while edits form a new selection.
        selection=req.model_dump();key=hashlib.sha256(json.dumps(selection,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:16]
        previous=next((value for value in item['approved'] if value['selection_id']==key),None)
        if previous:return previous
        name=f'sample-{identifier[:16]}-{key}'
        result=dict(selection_id=key,**selection)
        if req.use in ('quote','voice_reference'):
            target=catalog.root/'approved'/(name+'.wav')
            cut_audio(catalog.derived(identifier)/'audio.wav',target,req.start,req.end)
            if req.use=='quote':
                with voice.lock:
                    existing=next((entry for entry in voice.store.library() if entry['id']==name),None)
                    entry=existing or voice.register(target,name,req.text,'quote',req.triggers,req.mood)
                result['library_id']=entry['id']
            else:
                destination=voice.store.root/'references'/(name+'.wav');shutil.copy2(target,destination)
                result['reference_file']='references/'+destination.name
                result['note']='Référence candidate exportée ; ne remplace pas automatiquement la voix active et n’entraîne pas le modèle.'
        result['export_id']=name
        catalog.update(identifier,state='approved',approved=item['approved']+[result])
        return result


def build_media_router():
    router=APIRouter(prefix='/api/media',dependencies=[Depends(require_control)])

    @router.get('')
    def catalog(catalog=Depends(get_media),worker=Depends(get_media_worker),voice=Depends(get_voice)):
        items=catalog.list()
        for item in items:
            for frame in item['media'].get('frames',[]):frame['url']=f"/api/media/{item['id']}/frames/{frame['index']}"
        return dict(items=items,worker=worker.status(),voice_references=voice.config.get('reference_by_mood',{}),
                    versions=overview(catalog,voice,items))

    @router.get('/versions')
    def versions(catalog=Depends(get_media),voice=Depends(get_voice)):
        return overview(catalog,voice)

    @router.get('/{identifier}/selections/{selection_id}/audio')
    def selection_audio(identifier:str,selection_id:str,catalog=Depends(get_media),voice=Depends(get_voice)):
        try:
            item=catalog.get(identifier)
            selection=next((entry for entry in item['approved'] if entry['selection_id']==selection_id),None)
            if selection is None:raise ValueError('Passage non validé.')
            path,_=audio_path(selection,voice)
            if not path.is_file():raise ValueError('Fichier introuvable.')
            return FileResponse(path,media_type='audio/wav',headers={'Cache-Control':'no-store'})
        except (ValueError,KeyError,OSError) as exc:
            raise HTTPException(404,'Audio du passage validé introuvable.') from exc

    @router.post('/options')
    def options(req:MediaOptions,catalog=Depends(get_media),worker=Depends(get_media_worker)):
        catalog.automatic(req.automatic)
        if req.automatic:worker.start()
        return worker.status()

    @router.post('/resume')
    def resume(catalog=Depends(get_media),worker=Depends(get_media_worker)):
        catalog.automatic(True);worker.start();return worker.status()

    @router.post('/retranscribe-legacy')
    def retranscribe_legacy(catalog=Depends(get_media),worker=Depends(get_media_worker)):
        queued=0
        with _review_lock:
            for item in catalog.list():
                media=item['media'];source=media.get('transcription',{}).get('engine')
                # Before provenance was stored, manual edits cleared word timestamps.
                legacy=source=='vosk' or (source is None and bool(media.get('words')))
                if item['state'] in ('review','error') and media.get('audio') and media.get('transcribed') and legacy:
                    queue_transcription(catalog,item);queued+=1
        if queued:worker.start()
        return dict(queued=queued)

    @router.post('/{identifier}/retry')
    def retry(identifier:str,req:Retry,catalog=Depends(get_media),worker=Depends(get_media_worker)):
        try:
            item=catalog.get(identifier)
            if item['state']=='processing':raise ValueError('Ce sample est déjà en cours d’analyse.')
            media=item['media']
            if req.retranscribe:
                if req.transcript is not None:raise ValueError('Choisir une transcription manuelle ou une nouvelle reconnaissance, pas les deux.')
                queue_transcription(catalog,item);worker.start();return {'status':'pending'}
            if req.transcript is not None:
                if not media.get('audio'):raise ValueError('Préparer d’abord la piste audio avec une première analyse.')
                text=req.transcript.strip()
                if text!=media.get('transcript',''):
                    media['words']=[]
                    media['transcription']={'engine':'manual','language':'fr'}
                media.update(transcript=text,transcribed=bool(text))
            catalog.update(identifier,state='pending',error='',media=media,progress={})
            worker.start();return {'status':'pending'}
        except ValueError as exc:raise HTTPException(400,str(exc)) from exc

    @router.post('/{identifier}/approve')
    async def approval(identifier:str,req:Approval,catalog=Depends(get_media),voice=Depends(get_voice)):
        try:return await asyncio.to_thread(approve,catalog,identifier,req,voice)
        except (ValueError,OSError,VoiceUnavailable) as exc:raise HTTPException(400,str(exc)) from exc

    @router.post('/{identifier}/reference')
    def activate_reference(identifier:str,req:ReferenceSelection,catalog=Depends(get_media),voice=Depends(get_voice)):
        try:
            with _review_lock:
                item=catalog.get(identifier)
                selection=next((entry for entry in item['approved'] if entry['selection_id']==req.selection_id),None)
                if not selection or selection.get('use')!='voice_reference':raise ValueError('Valider ce passage comme référence vocale avant de l’activer.')
                return voice.activate_reference(selection['reference_file'],selection['mood'])
        except (ValueError,OSError,KeyError) as exc:raise HTTPException(400,str(exc)) from exc

    @router.get('/{identifier}/frames/{index}')
    def frame(identifier:str,index:int,catalog=Depends(get_media)):
        try:
            item=catalog.get(identifier)
            if index not in {frame['index'] for frame in item['media'].get('frames',[])}:raise ValueError()
            path=catalog.derived(identifier)/f'frame-{index}.jpg'
            if not path.is_file():raise ValueError()
            return FileResponse(path,media_type='image/jpeg',headers={'Cache-Control':'no-store'})
        except ValueError as exc:raise HTTPException(404,'Image introuvable') from exc

    @router.get('/{identifier}/audio')
    def audio(identifier:str,catalog=Depends(get_media)):
        try:
            catalog.get(identifier);path=catalog.derived(identifier)/'audio.wav'
            if not path.is_file():raise ValueError()
            return FileResponse(path,media_type='audio/wav',headers={'Cache-Control':'no-store'})
        except ValueError as exc:raise HTTPException(404,'Audio pas encore préparé') from exc

    return router
