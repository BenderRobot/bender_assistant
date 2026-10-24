"""RSS bulletins prepared by a separate CPU worker, played only on request."""
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import sqlite3
import time
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
import uuid
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo
from .processes import process_exists

DEFAULTS=dict(enabled=False,time='06:00',timezone='Europe/Paris',mood='excited',feeds=[],max_items=8)


class Text(HTMLParser):
    def __init__(self):super().__init__();self.parts=[]
    def handle_data(self,data):self.parts.append(data)


def clean(value,limit=400):
    parser=Text();parser.feed(value or '')
    return ' '.join(' '.join(parser.parts).split())[:limit]


def feed_url(value):
    parsed=urlsplit(value)
    if len(value)>2048 or parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Choisir une URL RSS HTTP ou HTTPS sans identifiants')
    return value


def fetch_feed(url,now):
    request=Request(feed_url(url),headers={'User-Agent':'BenderRSS/1.0'})
    with urlopen(request,timeout=15) as response:
        feed_url(response.geturl())
        data=response.read(1_000_001)
    if len(data)>1_000_000 or b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
        raise ValueError('Flux trop volumineux ou XML non pris en charge')
    return parse_feed(data,url,now)


def parse_feed(data,url,now):
    declarations=data.replace(b'\x00',b'').upper()
    if len(data)>1_000_000 or b'<!DOCTYPE' in declarations or b'<!ENTITY' in declarations:
        raise ValueError('XML RSS non pris en charge')
    root=ET.fromstring(data);atom={'a':'http://www.w3.org/2005/Atom'}
    is_atom=root.tag.endswith('}feed')
    entries=root.findall('a:entry',atom) if is_atom else root.findall('./channel/item')
    source=clean(root.findtext('a:title',default='',namespaces=atom) if is_atom else root.findtext('./channel/title',''),100) or urlsplit(url).hostname
    result=[]
    for entry in entries[:30]:
        if is_atom:
            title=entry.findtext('a:title',default='',namespaces=atom)
            summary=entry.findtext('a:summary',default='',namespaces=atom)
            date=entry.findtext('a:published',default='',namespaces=atom) or entry.findtext('a:updated',default='',namespaces=atom)
            link=next((node.get('href','') for node in entry.findall('a:link',atom) if node.get('rel','alternate')=='alternate'),'')
        else:title,summary,date,link=(entry.findtext(key,'') for key in ('title','description','pubDate','link'))
        published=None
        if date:
            try:published=datetime.fromisoformat(date.replace('Z','+00:00')) if is_atom else parsedate_to_datetime(date)
            except (ValueError,TypeError):pass
        if published:
            if published.tzinfo is None:published=published.replace(tzinfo=timezone.utc)
            if published<now-timedelta(hours=24) or published>now+timedelta(minutes=15):continue
        title=clean(title,220)
        if title:result.append(dict(title=title,summary=clean(summary,240),source=source,
                                    url=link if urlsplit(link).scheme in ('http','https') else url,
                                    published=published.isoformat() if published else None))
    return result


def chunks(text,limit=230):
    words=text.split();result=[];current=''
    for word in words:
        if len(word)>limit:raise ValueError('Mot trop long pour la synthèse')
        if current and len(current)+1+len(word)>limit:result.append(current);current=''
        current=(current+' '+word).strip()
    if current:result.append(current)
    return result


def news_request(text):
    from .service import normalized
    value=normalized(text)
    return value in {'les infos','les actualites','les nouvelles du jour','les infos du jour','mon bulletin'} or any(
        phrase in value for phrase in ('lis moi les infos','lis moi les informations','donne moi les infos','donne moi les actualites','lis les infos','lis moi les actualites','bulletin du jour','bulletin d informations'))


class Bulletins:
    def __init__(self,voice,now=None):
        self.voice=voice;self.root=voice.store.root/'bulletins';self.root.mkdir(exist_ok=True)
        self.clock=now or (lambda:datetime.now(timezone.utc))
        self.db=self.root/'jobs.sqlite3'
        with self.connect() as db:db.execute('''CREATE TABLE IF NOT EXISTS jobs (
            day TEXT PRIMARY KEY, state TEXT NOT NULL, text TEXT NOT NULL DEFAULT '',
            sources TEXT NOT NULL DEFAULT '[]', segments TEXT NOT NULL DEFAULT '[]',
            done INTEGER NOT NULL DEFAULT 0,total INTEGER NOT NULL DEFAULT 0,
            updated REAL NOT NULL,error TEXT NOT NULL DEFAULT '',owner INTEGER)''')

    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.db,timeout=15);db.row_factory=sqlite3.Row
        try:
            with db:yield db
        finally:db.close()

    def settings(self):
        path=self.root/'settings.json'
        return {**DEFAULTS,**(json.loads(path.read_text(encoding='utf-8')) if path.exists() else {})}

    def configure(self,value):
        result={**DEFAULTS,**value};ZoneInfo(result['timezone'])
        if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',result['time']):raise ValueError('Heure invalide')
        if result['mood'] not in ('neutral','sarcastic','angry','excited','sad'):raise ValueError('Humeur invalide')
        if len(result['feeds'])>6 or not 1<=result['max_items']<=8:raise ValueError('Maximum six flux et huit titres')
        result['feeds']=list(dict.fromkeys(feed_url(url.strip()) for url in result['feeds'] if url.strip()))
        if result['enabled'] and not result['feeds']:raise ValueError('Choisir au moins un flux avant de planifier')
        path=self.root/'settings.json';temp=self.root/(uuid.uuid4().hex+'.tmp')
        try:temp.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8');temp.replace(path)
        finally:temp.unlink(missing_ok=True)
        return result

    def day(self):return self.clock().astimezone(ZoneInfo(self.settings()['timezone'])).date().isoformat()

    def today(self):
        with self.connect() as db:row=db.execute('SELECT * FROM jobs WHERE day=?',(self.day(),)).fetchone()
        if not row:return dict(day=self.day(),state='absent',done=0,total=0,sources=[],segments=[])
        value=dict(row)
        for key in ('sources','segments'):value[key]=json.loads(value[key])
        value.pop('owner',None)
        return value

    def queue(self):
        if not self.settings()['feeds']:raise ValueError('Choisir les flux RSS avant de préparer')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT state FROM jobs WHERE day=?',(self.day(),)).fetchone()
            if not row or row['state']=='error':
                db.execute("INSERT OR REPLACE INTO jobs(day,state,updated) VALUES (?,'queued',?)",(self.day(),time.time()))
        return self.today()

    def update(self,_day=None,**values):
        with self.connect() as db:
            db.execute('UPDATE jobs SET '+','.join(key+'=?' for key in values)+',updated=? WHERE day=?',
                       (*[json.dumps(value,ensure_ascii=False) if key in ('sources','segments') else value for key,value in values.items()],time.time(),_day or self.day()))

    def run_due(self,fetch=fetch_feed):
        settings=self.settings();local=self.clock().astimezone(ZoneInfo(settings['timezone']));day=local.date().isoformat()
        state=self.today()
        if state['state']=='absent' and settings['enabled'] and local.strftime('%H:%M')>=settings['time']:
            self.queue();state=self.today()
        if state['state']=='processing':
            with self.connect() as db:row=db.execute('SELECT owner FROM jobs WHERE day=?',(self.day(),)).fetchone()
            if not row or not process_exists(row['owner']):
                self.update(state='error',error='Préparation interrompue. Relancer depuis l’atelier.')
            return self.today()
        if state['state']!='queued':return state
        with self.connect() as db:
            changed=db.execute("UPDATE jobs SET state='processing',owner=?,updated=? WHERE day=? AND state='queued'",(os.getpid(),time.time(),self.day())).rowcount
        if not changed:return self.today()
        try:
            items=[];errors=[];seen=set()
            # Round-robin gives each selected publisher a place in the bulletin.
            feeds=[]
            for url in settings['feeds']:
                try:feeds.append(fetch(url,self.clock()))
                except Exception:errors.append('Flux indisponible : '+url)
            for index in range(30):
                for feed in feeds:
                    if index<len(feed):
                        item=feed[index];key=item['title'].casefold()
                        if key not in seen:seen.add(key);items.append(item)
                if len(items)>=settings['max_items']:break
            items=items[:settings['max_items']]
            if not items:raise ValueError('Aucun titre exploitable dans les flux choisis')
            introduction=f"Voici les titres du {local.strftime('%d/%m/%Y')}, relevés à {local.strftime('%H:%M')}. "
            text=introduction+' '.join(f"D’après {item['source']}, {item['title']}. {item['summary']}" for item in items)
            parts=chunks(text);segments=[]
            self.update(_day=day,text=text,sources=items,total=len(parts),error=' ; '.join(errors))
            for part in parts:
                segment=self.voice.prepare_offline(part,settings['mood'])
                if segment['source']!='chatterbox':raise ValueError('La préparation exige Chatterbox')
                segments.append(segment);self.update(_day=day,done=len(segments),segments=segments)
            self.update(_day=day,state='ready')
        except Exception as error:self.update(_day=day,state='error',error=str(error)[:800])
        return self.today()

    def playback(self):
        item=self.today()
        if item['state']!='ready':raise ValueError('Le bulletin du jour n’est pas encore prêt. Consulte sa progression dans l’atelier.')
        for segment in item['segments']:
            if not self.voice.asset(segment['id'],'wav').is_file() or not self.voice.asset(segment['id'],'json').is_file():
                raise ValueError('Un fichier du bulletin manque ; aucune nouvelle génération lancée')
        return dict(text=item['text'],segments=[{**s,'cached':True} for s in item['segments']],warnings=[],usage=self.voice.store.usage())

    def answer(self,message):
        if not news_request(message):return None
        try:return dict(response=self.today()['text'],speech=self.playback(),prepared_bulletin=True)
        except ValueError as error:return dict(response=str(error),prepared_bulletin=True)
