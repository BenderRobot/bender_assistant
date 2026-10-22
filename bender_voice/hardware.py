"""Périphériques du serveur Debian ; captures uniquement sur demande."""
import json
import os
import re
import secrets
import shutil
import subprocess
import tempfile
import threading
import uuid
import wave
from pathlib import Path

from .config import inside


class HardwareError(RuntimeError):
    pass


class HardwareBusy(HardwareError):
    pass


class Hardware:
    def __init__(self, config):
        self.config = config
        self.settings = config.get('hardware', {})
        self.root = Path(config['data_dir']) / 'hardware'
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.model = None

    def control_token(self):
        supplied = os.getenv('BENDER_CONTROL_TOKEN', '')
        if supplied:
            if len(supplied) < 20:
                raise HardwareError('BENDER_CONTROL_TOKEN doit contenir au moins 20 caractères')
            return supplied
        path = self.root / 'control-token'
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            token = path.read_text(encoding='utf-8').strip()
            if len(token) < 20:
                raise HardwareError('Clé de contrôle locale invalide')
            return token
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            token = secrets.token_urlsafe(32)
            out.write(token)
        return token

    def authorized(self, token):
        return secrets.compare_digest(token.encode(), self.control_token().encode())

    @property
    def model_dir(self):
        return inside(self.config['data_dir'], self.settings.get('vosk_model_dir', 'models/vosk-fr'))

    def status(self):
        return {'microphone': self.settings.get('input_device', 'plughw:CARD=HD3000,DEV=0'),
                'speaker': self.settings.get('output_device', 'plughw:CARD=PCH,DEV=0'),
                'camera': self.settings.get('camera_device', '/dev/video0'),
                'arecord_installed': bool(shutil.which('arecord')), 'aplay_installed': bool(shutil.which('aplay')),
                'ffmpeg_installed': bool(shutil.which('ffmpeg')), 'vosk_model_ready': (self.model_dir / 'am').is_dir(),
                'recording': self.lock.locked(), 'control_key_required': True}

    def transcribe(self, path):
        if not (self.model_dir / 'am').is_dir():
            raise HardwareError('Modèle Vosk français absent : lancer download-models vosk')
        try:
            from vosk import Model, KaldiRecognizer, SetLogLevel
            SetLogLevel(-1)
            if self.model is None:
                self.model = Model(str(self.model_dir))
            pieces = []
            with wave.open(str(path), 'rb') as wav:
                recognizer = KaldiRecognizer(self.model, wav.getframerate())
                while True:
                    data = wav.readframes(4000)
                    if not data:
                        break
                    if recognizer.AcceptWaveform(data):
                        pieces.append(json.loads(recognizer.Result()).get('text', ''))
                pieces.append(json.loads(recognizer.FinalResult()).get('text', ''))
            return ' '.join(p for p in pieces if p).strip()
        except ImportError as exc:
            raise HardwareError('Installer les dépendances de requirements-io.txt') from exc
        except Exception as exc:
            raise HardwareError('Reconnaissance Vosk impossible ; vérifier le modèle français') from exc

    def listen(self, seconds=6):
        if not isinstance(seconds, int) or not 2 <= seconds <= 15:
            raise ValueError('Durée comprise entre 2 et 15 secondes')
        if not shutil.which('arecord'):
            raise HardwareError('arecord absent : installer alsa-utils sur Debian')
        if not (self.model_dir / 'am').is_dir():
            raise HardwareError('Modèle Vosk français absent : lancer download-models vosk')
        if not self.lock.acquire(blocking=False):
            raise HardwareBusy('Une capture est déjà en cours')
        try:
            with tempfile.TemporaryDirectory(dir=self.root) as directory:
                path = Path(directory) / 'micro.wav'
                try:
                    subprocess.run(['arecord', '-q', '-D', self.status()['microphone'], '-f', 'S16_LE',
                                    '-r', '16000', '-c', '1', '-d', str(seconds), str(path)],
                                   capture_output=True, check=True, timeout=seconds + 5)
                except (OSError, subprocess.SubprocessError) as exc:
                    raise HardwareError('Capture micro impossible ; vérifier la LifeCam et les droits audio') from exc
                text = self.transcribe(path)
                return {'text': text, 'engine': 'vosk-local', 'seconds': seconds,
                        'warning': '' if text else 'Aucune parole reconnue ; rapproche-toi du micro et réessaie'}
        finally:
            self.lock.release()

    def photo_path(self, identifier):
        if not re.fullmatch(r'[a-f0-9]{32}', identifier):
            raise ValueError('Identifiant photo invalide')
        return self.root / f'snapshot-{identifier}.jpg'

    def capture(self):
        if not shutil.which('ffmpeg'):
            raise HardwareError('ffmpeg absent sur le serveur')
        if not self.lock.acquire(blocking=False):
            raise HardwareBusy('Une capture est déjà en cours')
        identifier = uuid.uuid4().hex
        path = self.photo_path(identifier)
        try:
            try:
                subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'v4l2',
                                '-input_format', 'mjpeg', '-video_size', '640x480',
                                '-i', self.status()['camera'], '-frames:v', '1', '-update', '1', str(path)],
                               capture_output=True, check=True, timeout=12)
            except (OSError, subprocess.SubprocessError) as exc:
                raise HardwareError('Caméra indisponible ; vérifier /dev/video0 et les droits vidéo') from exc
            if not path.is_file() or not 0 < path.stat().st_size <= 4_000_000:
                raise HardwareError('Image caméra invalide')
            photos = sorted(self.root.glob('snapshot-*.jpg'), key=lambda p: p.stat().st_mtime, reverse=True)
            for old in photos[3:]:
                old.unlink(missing_ok=True)
            return {'id': identifier, 'image_url': f'/api/hardware/photos/{identifier}', 'width': 640, 'height': 480}
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        finally:
            self.lock.release()
