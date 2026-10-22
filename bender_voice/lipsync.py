import array
import json
import logging
import math
import sys
import wave
from pathlib import Path

from .config import inside


def read_wav(path):
    with wave.open(str(path), 'rb') as wav:
        if wav.getsampwidth() != 2 or wav.getnchannels() not in (1, 2):
            raise ValueError('Audio attendu : WAV PCM16 mono ou stéréo')
        rate, channels = wav.getframerate(), wav.getnchannels()
        samples = array.array('h', wav.readframes(wav.getnframes()))
        if sys.byteorder != 'little':
            samples.byteswap()
    return samples[::channels], rate


def validate_timeline(data, duration):
    cues = data.get('cues')
    if not isinstance(cues, list) or not cues:
        raise ValueError('Une timeline doit contenir des cues')
    previous = -1
    for cue in cues:
        t, pose = cue.get('t'), cue.get('pose')
        if not isinstance(t, (int, float)) or isinstance(t, bool) or not math.isfinite(t) or not 0 <= t <= duration + .05 or t < previous:
            raise ValueError('Horaires de timeline invalides')
        if not isinstance(pose, int) or isinstance(pose, bool) or not 0 <= pose <= 11:
            raise ValueError('Pose de timeline invalide')
        previous = t
    return {**data, 'duration': duration}


class LipSync:
    def __init__(self, config):
        self.config = config
        self.model = None
        self.families = json.loads((Path(__file__).with_name('visemes-fr.json')).read_text(encoding='utf-8-sig'))['families']

    def _family(self, phone):
        import unicodedata
        aliases = {'ɐ': 'a', 'ɒ': 'ɔ', 'ɪ': 'i', 'ʊ': 'u', 'ɹ': 'ʁ', 'r': 'ʁ', 'ɾ': 'ʁ', 'ɡ': 'g'}
        token = phone.replace('ː', '').replace('ˈ', '').replace('ˌ', '')
        for variant in (token, aliases.get(token, token), ''.join(c for c in unicodedata.normalize('NFD', token) if not unicodedata.combining(c))):
            for family in self.families:
                if variant in family['phonemes']:
                    return family['id'], family['pose']
        return 'UNKNOWN', 5

    def build(self, path):
        samples, rate = read_wav(path)
        duration = len(samples) / rate
        frames = []
        step = max(1, int(rate * .04))
        for i in range(0, len(samples), step):
            chunk = samples[i:i + step]
            rms = math.sqrt(sum(v * v for v in chunk) / max(1, len(chunk))) / 32768
            frames.append((i / rate, rms))
        peak = max([v for _, v in frames] + [.01])
        cues = [{'t': 0, 'pose': 0, 'family': 'REST'}]
        for t, rms in frames:
            level = rms / peak
            active = rms > max(.006, peak * .06)
            pose = 11 if level > .85 else 2 if level > .45 else 4 if level > .25 else 5
            cues.append({'t': round(t, 4), 'pose': pose if active else 0,
                         'family': 'ACOUSTIC_FALLBACK' if active else 'REST_ESTIMATED'})
        warnings = []
        if self.config.get('lipsync', {}).get('engine') == 'allosaurus':
            try:
                from allosaurus.app import read_recognizer
                folder = inside(self.config['data_dir'], self.config['lipsync'].get('allosaurus_model_dir', 'models/allosaurus'))
                if not (folder / 'uni2005').is_dir():
                    raise RuntimeError('Modèle phonétique local absent')
                if self.model is None:
                    self.model = read_recognizer('uni2005', alt_model_path=folder)
                raw = self.model.recognize(str(path), lang_id='fra', timestamp=True)
                phones = []
                for line in raw.splitlines():
                    start, _, phone = line.split()
                    family, pose = self._family(phone)
                    phones.append({'t': float(start), 'pose': pose, 'phone': phone, 'family': family})
                for i, cue in enumerate(phones):
                    end = min(cue['t'] + .20, phones[i + 1]['t'] if i + 1 < len(phones) else duration)
                    cues = [c for c in cues if not cue['t'] <= c['t'] < end]
                    cues.append(cue)
                    # Reprendre explicitement l'acoustique à la fin de la tenue reconnue.
                    nearest = min(frames, key=lambda f: abs(f[0] - end), default=(end, 0))[1] / peak
                    cues.append({'t': min(end, duration), 'pose': 2 if nearest > .45 else 5 if nearest > .06 else 0,
                                 'family': 'ACOUSTIC_FALLBACK'})
            except Exception:
                logging.getLogger(__name__).exception('Moteur phonétique indisponible ; repli acoustique')
                warnings.append('Reconnaissance phonétique indisponible : animation acoustique estimée')
        else:
            warnings.append('Animation acoustique estimée ; phonèmes non reconnus')
        cues.append({'t': duration, 'pose': 0, 'family': 'REST'})
        cues.sort(key=lambda c: c['t'])
        compact = []
        for cue in cues:
            if compact and all(compact[-1].get(k) == cue.get(k) for k in ('pose', 'family', 'phone')):
                continue
            compact.append(cue)
        if compact[-1]['t'] != duration:
            compact.append({'t': duration, 'pose': 0, 'family': 'REST'})
        return validate_timeline({'version': 1, 'cues': compact, 'warnings': warnings}, duration)
