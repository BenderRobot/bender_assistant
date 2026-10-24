"""Explicit, owner-editable mood reactions; no automatic emotion inference."""
import json
from pathlib import Path
import random
import re
import threading
import unicodedata
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Literal
from pose_models import EyesShape

Mood=Literal['neutral','sarcastic','angry','excited','sad']
Eyes=Literal['normal','angry','happy','surprised','sleepy','sad','worried','crying',
             'ref1','ref2','ref3','ref4','ref5']
LABELS={'neutral':'Neutre','sarcastic':'Sarcastique','angry':'Agacé','excited':'Énergique','sad':'Triste'}


class Scenario(BaseModel):
    model_config=ConfigDict(extra='forbid')
    id:str=Field(pattern=r'^[a-z0-9_-]{1,64}$')
    mood:Mood
    intensity:int=Field(ge=1,le=3)
    name:str=Field(min_length=1,max_length=100)
    text:str=Field(min_length=1,max_length=1000)
    eyes:Eyes='normal'
    custom_eyes:EyesShape|None=None
    library_id:str|None=Field(default=None,pattern=r'^[a-z0-9][a-z0-9_-]{0,63}$')
    enabled:bool=True

    @field_validator('name','text')
    @classmethod
    def nonempty(cls,value):
        value=value.strip()
        if not value:raise ValueError('Un nom et une phrase sont requis.')
        return value


class ScenarioCatalog(BaseModel):
    revision:int=Field(ge=1)
    items:list[Scenario]=Field(max_length=150)


class ScenarioConflict(ValueError):pass


def command(text):
    value=' '.join(''.join(c for c in unicodedata.normalize('NFD',text.lower().replace('’',"'")) if not unicodedata.combining(c)).split())
    value=value.strip(' .,!?')
    value=re.sub(r'^bender[, ]+','',value)
    value=re.sub(r'[, ]+(?:s il te plait|s\x27il te plait|stp)$','',value)
    match=re.fullmatch(r'(?:sois|fais le|passe en mode|mets.toi en mode|humeur) '
                      r'(?:(un peu|legerement|tres|vraiment|extremement) )?'
                      r'(triste|sarcastique|agace|enerve|en colere|furieux|joyeux|heureux|content|enthousiaste|energique|neutre|normal|calme)'
                      r'(?: (?:niveau|intensite) ([123]))?',value)
    if not match:return None
    modifier,adjective,level=match.groups()
    mood=('sad' if adjective=='triste' else 'sarcastic' if adjective=='sarcastique' else
          'angry' if adjective in ('agace','enerve','en colere','furieux') else
          'neutral' if adjective in ('neutre','normal','calme') else 'excited')
    intensity=int(level) if level else 1 if modifier in ('un peu','legerement') else 3 if modifier in ('tres','vraiment','extremement') or adjective=='furieux' else 2
    return mood,intensity


class MoodScenarios:
    def __init__(self,root):
        self.path=Path(root)/'mood-scenarios.json'
        self.lock=threading.RLock();self.last={}

    def catalog(self):
        with self.lock:
            path=self.path if self.path.is_file() else Path(__file__).with_name('mood-scenarios.json')
            return ScenarioCatalog.model_validate_json(path.read_text(encoding='utf-8-sig')).model_dump()

    def save(self,scenario,revision,copy=False):
        with self.lock:
            data=self.catalog()
            if revision!=data['revision']:raise ScenarioConflict('Les scénarios ont changé ; recharge avant d’enregistrer.')
            item=scenario.model_dump()
            if copy:item['id']=uuid.uuid4().hex
            index=next((i for i,value in enumerate(data['items']) if value['id']==item['id']),None)
            if index is None:data['items'].append(item)
            else:data['items'][index]=item
            data['revision']+=1
            validated=ScenarioCatalog.model_validate(data).model_dump()
            self.path.parent.mkdir(parents=True,exist_ok=True)
            temporary=self.path.with_suffix('.tmp')
            temporary.write_text(json.dumps(validated,ensure_ascii=False,indent=2),encoding='utf-8')
            temporary.replace(self.path)
            return validated

    def pick(self,mood,intensity):
        with self.lock:
            options=[item for item in self.catalog()['items'] if item['mood']==mood
                     and item['intensity']==intensity and item['enabled']]
            if not options:raise ValueError('Aucun scénario actif pour cette humeur et ce niveau.')
            previous=self.last.get((mood,intensity))
            selected=random.choice([item for item in options if item['id']!=previous] or options)
            self.last[mood,intensity]=selected['id']
            return selected


def reply(store,voice,mood,intensity,mode='auto',speech=True):
    scenario=store.pick(mood,intensity)
    text=scenario['text'];bundle=None
    if scenario['library_id']:
        with voice.lock:
            entry=next((entry for entry in voice.store.library() if entry['id']==scenario['library_id']
                        and entry.get('enabled',True)),None)
            if not entry:raise ValueError('La réplique du scénario est absente ou désactivée ; choisir une autre réplique.')
            text=entry.get('text','')
            if speech:bundle={'text':text,'segments':[voice._library_segment(entry)],'warnings':[]}
    elif speech:
        bundle=voice.prepare(text,mode,mood)
    if bundle:
        face={'eyes':scenario['eyes'],'custom_eyes':scenario['custom_eyes']}
        # Playback metadata only. Never change the shared audio/timeline cache.
        bundle={**bundle,'segments':[{**segment,'face_override':face} for segment in bundle['segments']]}
    result={'response':text,'mood_scenario':{k:scenario[k] for k in ('id','name','mood','intensity','eyes')},
            'timings':{'brain_seconds':0,'brain_source':'local'},
            'note':'L’intensité choisit la phrase et les yeux. La prosodie dépend du moteur de voix et de sa référence.'}
    if bundle:result['speech']=bundle
    return result
