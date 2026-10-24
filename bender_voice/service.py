import hashlib
import json
import random
import re
import threading
import time
import unicodedata
import uuid
from pathlib import Path

from .config import inside
from .lipsync import LipSync, read_wav, validate_timeline
from .providers import ChatterboxVoice, ElevenVoice, SystemVoice, VoiceUnavailable, convert_audio
from .store import Store


def normalized(text):
    text = ''.join(c for c in unicodedata.normalize('NFD', text.casefold()) if not unicodedata.combining(c))
    return ' '.join(re.findall(r'\w+', text))


class VoiceService:
    def __init__(self, config, providers=None):
        self.config = config
        self.store = Store(config['data_dir'])
        self.lips = LipSync(config)
        self.providers = providers or {'chatterbox': ChatterboxVoice(config), 'system': SystemVoice(config), 'elevenlabs': ElevenVoice(config)}
        self.lock = threading.RLock()  # Une seule synthèse et réservation par processus.

    def activate_reference(self,reference,mood='neutral'):
        from . import references
        with self.lock:
            references.validate(self.store.root,{mood:reference})
            if not inside(self.store.root,reference).is_file():raise ValueError('Fichier de référence vocale absent.')
            selected={**references.read(self.store.root),mood:reference}
            references.save(self.store.root,selected)
            self.config['reference_by_mood']={**self.config.get('reference_by_mood',{}),**selected}
            self.config['local_provider']='chatterbox'
            return dict(mood=mood,reference_file=reference,provider='chatterbox',
                        note='Référence Chatterbox activée. Teste une phrase nouvelle en mode Local ; le modèle Chatterbox doit être installé.')

    def _key(self, text, provider, mood):
        value = {'text': text, 'mood': mood, 'voice': provider.identity(mood),
                 'lipsync': self.config.get('lipsync', {}), 'cache_version': self.config.get('cache_version', 1)}
        return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    def asset(self, identifier, suffix):
        if not re.fullmatch(r'[a-f0-9]{64}', identifier) or suffix not in ('wav', 'json'):
            raise ValueError('Identifiant audio invalide')
        return self.store.root / 'cache' / f'{identifier}.{suffix}'

    def _segment(self, key, source, cached=False, warnings=None):
        metadata = json.loads(self.asset(key, 'json').read_text(encoding='utf-8'))
        return {'id': key, 'source': source, 'cached': cached,
                'text': metadata.get('text', ''), 'eyes': metadata.get('eyes', 'normal'),
                'audio_url': f'/api/voice/assets/{key}.wav', 'timeline_url': f'/api/voice/assets/{key}.json',
                'duration': metadata['duration'], 'warnings': (warnings or []) + metadata.get('warnings', [])}

    def _generate(self, text, mood, provider, warnings):
        key = self._key(text, provider, mood)
        if self.asset(key, 'wav').is_file() and self.asset(key, 'json').is_file():
            return self._segment(key, provider.name, cached=True, warnings=warnings)
        if provider.name == 'elevenlabs':
            if not provider.available():
                raise VoiceUnavailable('ElevenLabs désactivé ou non configuré')
            limit = self.config.get('elevenlabs', {}).get('daily_character_limit', 2000)
            if not self.store.reserve(len(text), limit, self.config.get('elevenlabs', {}).get('monthly_character_limit', 25000)):
                raise VoiceUnavailable('Plafond quotidien ou mensuel ElevenLabs atteint')
        temp = self.store.root / 'cache' / f'tmp-{uuid.uuid4().hex}.wav'
        try:
            alignment = provider.synthesize(text, mood, temp)
            timeline = self.lips.build(temp)
            timeline.update({'text': text, 'provider': provider.name, 'eyes': 'normal'})
            if alignment:
                timeline['character_alignment'] = alignment  # Caractères, pas des phonèmes.
            temp.replace(self.asset(key, 'wav'))
            self.asset(key, 'json').write_text(json.dumps(timeline, ensure_ascii=False), encoding='utf-8')
        finally:
            temp.unlink(missing_ok=True)
        return self._segment(key, provider.name, warnings=warnings)

    def _library_segment(self, entry):
        source = inside(self.store.root / 'library', entry['audio'])
        if not source.is_file():
            raise VoiceUnavailable('Fichier de bibliothèque absent')
        raw = source.read_bytes()
        timeline_path = inside(self.store.root / 'library', entry['timeline']) if entry.get('timeline') else None
        timeline_raw = timeline_path.read_bytes() if timeline_path else b''
        key = hashlib.sha256(raw + timeline_raw + json.dumps(entry, sort_keys=True).encode()).hexdigest()
        if not self.asset(key, 'json').is_file() or not self.asset(key, 'wav').is_file():
            convert_audio(source, self.asset(key, 'wav'))
            samples, rate = read_wav(self.asset(key, 'wav'))
            duration = len(samples) / rate
            timeline = validate_timeline(json.loads(timeline_raw.decode('utf-8-sig')), duration) if timeline_raw else self.lips.build(self.asset(key, 'wav'))
            timeline.update({'text': entry.get('text', ''), 'eyes': entry.get('eyes', 'normal'), 'provider': 'library'})
            self.asset(key, 'json').write_text(json.dumps(timeline, ensure_ascii=False), encoding='utf-8')
        return self._segment(key, 'library', cached=True)

    def _quote(self, entries, context, mood):
        options = self.config.get('quotes', {})
        now = time.time()
        if now - self.store.last_played('__quote__') < options.get('global_cooldown_seconds', 120):
            return None
        words = set(normalized(context).split())
        candidates = []
        for entry in entries:
            if entry.get('type') != 'quote' or not entry.get('enabled', True):
                continue
            if entry.get('moods') and mood not in entry['moods']:
                continue
            triggers = entry.get('triggers', [])
            if not triggers or not any(set(normalized(t).split()) <= words for t in triggers if normalized(t)):
                continue
            if now - self.store.last_played(entry['id']) < entry.get('cooldown_seconds', 3600):
                continue
            candidates.append(entry)
        if not candidates or random.random() >= options.get('probability', .2):
            return None
        entry = random.choice(candidates)
        segment = self._library_segment(entry)
        self.store.mark_played(entry['id'])
        self.store.mark_played('__quote__')
        return segment

    def prepare(self, text, mode='auto', mood='neutral', context='', topic='', allow_quote=False):
        text = text.strip()
        if not text or len(text) > 8000 or mode not in ('auto', 'local', 'cloud', 'cache'):
            raise ValueError('Texte vide/trop long ou mode invalide')
        if len(mood) > 40 or len(context) > 8000:
            raise ValueError('Contexte ou humeur invalide')
        with self.lock:
            warnings = []
            entries = self.store.library()
            primary = None
            for entry in entries:
                if entry.get('type') == 'basic' and entry.get('enabled', True) and normalized(entry.get('text', '')) == normalized(text):
                    try:
                        primary = self._library_segment(entry)
                        break
                    except (OSError, ValueError, VoiceUnavailable):
                        warnings.append('Réponse enregistrée indisponible ; génération de la phrase demandée')
            local_name = self.config.get('local_provider', 'chatterbox')
            cloud = self.providers['elevenlabs']
            # Tout cache compatible peut être rejoué avant de générer, même sans réseau/clé.
            if primary is None and mode in ('auto', 'cache'):
                for name in ('elevenlabs', local_name, 'system'):
                    if name=='system' and mode=='auto' and self.config.get('routing',{}).get('conversation_cloud',True) and self.config.get('elevenlabs',{}).get('enabled'):
                        continue
                    provider = self.providers[name]
                    key = self._key(text, provider, mood)
                    if self.asset(key, 'wav').is_file() and self.asset(key, 'json').is_file():
                        primary = self._segment(key, name, cached=True)
                        break
            if primary is None:
                if mode == 'cache':
                    raise VoiceUnavailable('Aucun enregistrement en cache pour cette phrase et cette voix')
                routing=self.config.get('routing',{})
                live_cloud=routing.get('conversation_cloud',True)
                cloud_wanted = mode == 'cloud' or (mode == 'auto' and (live_cloud or topic in ('news', 'narration')) and self.config.get('elevenlabs', {}).get('enabled'))
                order = ['elevenlabs'] if cloud_wanted else []
                if mode=='local' or (mode=='auto' and not live_cloud) or routing.get('slow_fallback',False):
                    order.append(local_name)
                elif not cloud_wanted:
                    warnings.append('Conversation : ElevenLabs non activé. Chatterbox est réservé à la préparation ; aucun calcul lent lancé.')
                if self.config.get('system_fallback', True) and 'system' not in order:
                    order.append('system')
                for name in order:
                    try:
                        primary = self._generate(text, mood, self.providers[name], warnings)
                        break
                    except VoiceUnavailable as exc:
                        warnings.append(str(exc))
                if primary is None:
                    raise VoiceUnavailable('; '.join(warnings))
            segments = [primary]
            if allow_quote:
                try:
                    quote = self._quote(entries, context, mood)
                    if quote:
                        segments.append(quote)
                except (OSError, KeyError, ValueError, VoiceUnavailable):
                    warnings.append('Réplique contextuelle ignorée : fichier ou catalogue invalide')
            return {'text': text, 'segments': segments, 'warnings': warnings, 'usage': self.store.usage()}

    def prepare_offline(self,text,mood='neutral'):
        """Worker only: no API call and no generic-voice fallback."""
        if not text.strip() or len(text)>8000:raise ValueError('Texte de préparation invalide')
        with self.lock:
            segment=self._generate(text.strip(),mood,self.providers['chatterbox'],[])
            return segment

    def register(self, source, identifier, text, kind='quote', triggers=None, mood=None, timeline=None, eyes='normal'):
        if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}', identifier) or kind not in ('quote', 'basic'):
            raise ValueError('Identifiant ou type invalide')
        if eyes not in ('normal', 'angry', 'happy', 'surprised', 'sleepy', 'sad', 'worried', 'crying', 'ref1', 'ref2', 'ref3', 'ref4', 'ref5'):
            raise ValueError('Expression des yeux inconnue')
        with self.lock:
            entries = self.store.library()
            if any(e['id'] == identifier for e in entries):
                raise ValueError('Cet identifiant existe déjà ; choisir un autre nom')
            audio_name = identifier + '.wav'
            destination = self.store.root / 'library' / audio_name
            convert_audio(source, destination)
            entry = {'id': identifier, 'type': kind, 'text': text, 'audio': audio_name,
                     'triggers': triggers or [], 'moods': [mood] if mood else [],
                     'eyes': eyes, 'cooldown_seconds': 3600, 'enabled': True}
            if timeline:
                samples, rate = read_wav(destination)
                parsed = validate_timeline(json.loads(Path(timeline).read_text(encoding='utf-8-sig')), len(samples) / rate)
                name = identifier + '.json'
                (self.store.root / 'library' / name).write_text(json.dumps(parsed, ensure_ascii=False), encoding='utf-8')
                entry['timeline'] = name
            entries.append(entry)
            (self.store.root / 'library' / 'catalog.json').write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding='utf-8')
            return entry
