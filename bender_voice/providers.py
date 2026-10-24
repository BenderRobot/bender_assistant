import base64
import hashlib
import os
import shutil
import subprocess

from .config import inside


class VoiceUnavailable(RuntimeError):
    pass


def convert_audio(source, target):
    try:
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', str(source),
                        '-ac', '1', '-ar', '24000', '-c:a', 'pcm_s16le', str(target)],
                       check=True, capture_output=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        raise VoiceUnavailable('Conversion audio impossible ; vérifier ffmpeg et le fichier source') from exc


class SystemVoice:
    name = 'system'

    def __init__(self, config):
        self.config = config

    def identity(self, mood):
        return {'provider': self.name, 'voice': 'espeak-ng-fr', 'version': 1}

    def synthesize(self, text, mood, target):
        binary = shutil.which('espeak-ng')
        if not binary:
            raise VoiceUnavailable('Installer espeak-ng ou configurer Chatterbox')
        try:
            subprocess.run([binary, '-v', 'fr-fr', '-s', '155', '-w', str(target), '--stdin'],
                           input=text.encode('utf-8'), capture_output=True, check=True, timeout=120)
        except subprocess.SubprocessError as exc:
            raise VoiceUnavailable('La voix système a échoué') from exc
        return None


class ChatterboxVoice:
    name = 'chatterbox'

    def __init__(self, config):
        self.config = config
        self.model = None

    def reference(self, mood):
        refs = self.config.get('reference_by_mood', {})
        return inside(self.config['data_dir'], refs.get(mood, refs.get('neutral', 'references/neutre.wav')))

    def identity(self, mood):
        reference = self.reference(mood)
        digest = hashlib.sha256(reference.read_bytes()).hexdigest() if reference.is_file() else 'missing'
        return {'provider': self.name, 'config': self.config.get('chatterbox', {}), 'reference_sha256': digest}

    def synthesize(self, text, mood, target):
        reference = self.reference(mood)
        settings = self.config.get('chatterbox', {})
        directory = inside(self.config['data_dir'], settings.get('model_dir', 'models/chatterbox'))
        if not reference.is_file() or not directory.is_dir():
            raise VoiceUnavailable('Chatterbox : référence vocale ou modèle local absent')
        try:
            from chatterbox.mtl_tts import ChatterboxMultilingualTTS
            import torchaudio
            if self.model is None:
                # Aucun téléchargement implicite pendant la génération.
                self.model = ChatterboxMultilingualTTS.from_local(directory, device=settings.get('device', 'cpu'))
            wav = self.model.generate(text, language_id='fr', audio_prompt_path=str(reference),
                                      exaggeration=float(settings.get('exaggeration', .5)),
                                      cfg_weight=float(settings.get('cfg_weight', .5)))
            torchaudio.save(str(target), wav, self.model.sr)
        except Exception as exc:
            raise VoiceUnavailable('Chatterbox indisponible ; vérifier ses dépendances et modèles locaux') from exc
        return None


class ElevenVoice:
    name = 'elevenlabs'

    def __init__(self, config):
        self.config = config

    def identity(self, mood):
        settings = self.config.get('elevenlabs', {})
        return {'provider': self.name, 'voice_id': settings.get('voice_id'),
                'model_id': settings.get('model_id', 'eleven_multilingual_v2'), 'format': 'mp3_44100_128'}

    def available(self):
        return bool(self.config.get('elevenlabs', {}).get('enabled') and
                    self.config['elevenlabs'].get('voice_id') and os.getenv('ELEVENLABS_API_KEY'))

    def synthesize(self, text, mood, target):
        if not self.available():
            raise VoiceUnavailable('ElevenLabs désactivé ou non configuré')
        settings = self.config['elevenlabs']
        temporary = target.with_suffix('.mp3')
        try:
            from elevenlabs import ElevenLabs
            import httpx

            # Un seul essai : éviter de facturer des générations en double.
            timeout = settings.get('timeout_seconds', 30)
            with httpx.Client(timeout=timeout) as transport:
                client = ElevenLabs(api_key=os.environ['ELEVENLABS_API_KEY'],
                                    httpx_client=transport, timeout=timeout)
                payload = client.text_to_speech.convert_with_timestamps(
                    voice_id=settings['voice_id'], text=text,
                    model_id=settings.get('model_id', 'eleven_multilingual_v2'),
                    output_format='mp3_44100_128',
                    request_options={'max_retries': 0},
                )
            temporary.write_bytes(base64.b64decode(payload.audio_base_64, validate=True))
            convert_audio(temporary, target)
            alignment = payload.normalized_alignment or payload.alignment
            return alignment.model_dump(mode='json') if alignment is not None else None
        except Exception as exc:
            # Do not expose SDK error bodies or credentials through API errors/logs.
            reason = 'La génération ElevenLabs a échoué'
            if getattr(exc, 'status_code', None) in (401, 403):
                reason = 'ElevenLabs : clé refusée ou permissions insuffisantes'
            elif getattr(exc, 'status_code', None) == 429:
                reason = 'ElevenLabs : limite du compte ou de requêtes atteinte'
            raise VoiceUnavailable(reason + ' ; aucun nouvel essai automatique') from None
        finally:
            temporary.unlink(missing_ok=True)
