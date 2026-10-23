"""Périphériques du serveur Debian ; captures uniquement sur demande."""
import json
import os
import re
import secrets
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
import wave
from pathlib import Path

from .config import inside


class HardwareError(RuntimeError):
    pass


class HardwareBusy(HardwareError):
    pass


class MicrophoneSession:
    """One bounded, user-controlled recording; raw PCM avoids truncated WAV headers."""
    ACTIVE = ('recording', 'stopping', 'transcribing')

    def __init__(self, hardware):
        self.hardware = hardware
        self.guard = threading.RLock()
        self.state = {'status': 'idle', 'session_id': ''}
        self.process = None
        self.started = 0
        self.cancelled = False
        self.thread = None

    def snapshot(self, identifier=None):
        with self.guard:
            if identifier is not None and identifier != self.state['session_id']:
                raise ValueError('Session micro inconnue ou remplacée')
            state = dict(self.state)
            if state['status'] in self.ACTIVE:
                state['elapsed'] = round(min(time.monotonic() - self.started, state['max_seconds']), 1)
            return state

    def start(self, max_seconds=60):
        if type(max_seconds) is not int or not 2 <= max_seconds <= 60:
            raise ValueError('Durée maximale comprise entre 2 et 60 secondes')
        hw = self.hardware
        if not shutil.which('arecord'):
            raise HardwareError('arecord absent : installer alsa-utils sur Debian')
        if not (hw.model_dir / 'am').is_dir():
            raise HardwareError('Modèle Vosk français absent : lancer download-models vosk')
        with self.guard:
            if self.state['status'] in self.ACTIVE or not hw.lock.acquire(blocking=False):
                raise HardwareBusy('Une capture est déjà en cours')
            try:
                process = subprocess.Popen(['arecord', '-q', '-D', hw.status()['microphone'],
                    '-t', 'raw', '-f', 'S16_LE', '-r', '16000', '-c', '1', '-d', str(max_seconds)],
                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            except OSError as exc:
                hw.lock.release()
                raise HardwareError('Capture micro impossible ; vérifier la LifeCam et les droits audio') from exc
            self.process = process
            self.started = time.monotonic()
            self.cancelled = False
            identifier = uuid.uuid4().hex
            self.state = dict(session_id=identifier, status='recording', elapsed=0, max_seconds=max_seconds,
                              text='', warning='', error='', engine='vosk-local', stop_reason='')
            self.thread = threading.Thread(target=self._record, args=(identifier, process, max_seconds), daemon=True)
            self.thread.start()
            return dict(self.state)

    @staticmethod
    def _halt(process):
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)

    def stop(self, identifier, cancel=False):
        with self.guard:
            self.snapshot(identifier)
            if self.state['status'] not in self.ACTIVE:
                return dict(self.state)
            self.cancelled = self.cancelled or cancel
            self.state['stop_reason'] = 'cancelled' if self.cancelled else 'manual'
            if self.state['status'] == 'recording':
                self.state['status'] = 'stopping'
            process = self.process
        if process is not None:
            self._halt(process)
        return self.snapshot(identifier)

    def _expire(self, identifier, process):
        with self.guard:
            if self.state['session_id'] != identifier or self.state['status'] not in self.ACTIVE:
                return
            if not self.state['stop_reason']:
                self.state['stop_reason'] = 'limit'
        self._halt(process)

    def _record(self, identifier, process, max_seconds):
        timer = threading.Timer(max_seconds + 2, self._expire, args=(identifier, process))
        timer.daemon = True
        timer.start()
        try:
            with tempfile.TemporaryDirectory(dir=self.hardware.root) as directory:
                path = Path(directory) / 'micro.wav'
                count = 0
                with wave.open(str(path), 'wb') as wav:
                    wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000)
                    while count < max_seconds * 32000:
                        chunk = process.stdout.read(min(4096, max_seconds * 32000 - count))
                        if not chunk:
                            break
                        wav.writeframesraw(chunk)
                        count += len(chunk)
                if count >= max_seconds * 32000:
                    self._expire(identifier, process)
                try:
                    result = process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self._expire(identifier, process)
                    result = process.returncode
                with self.guard:
                    self.state['elapsed'] = round(min(time.monotonic() - self.started, max_seconds), 1)
                    if self.cancelled:
                        self.state['status'] = 'cancelled'
                        return
                    if result != 0 and not self.state['stop_reason']:
                        raise HardwareError('Capture micro impossible ; vérifier la LifeCam et les droits audio')
                    self.state['stop_reason'] = self.state['stop_reason'] or 'limit'
                    self.state['status'] = 'transcribing'
                timer.cancel()
                text = self.hardware.transcribe(path) if count >= 1600 else ''
                with self.guard:
                    if self.cancelled:
                        self.state['status'] = 'cancelled'
                    else:
                        self.state.update(status='finished', text=text,
                            warning='' if text else 'Aucune parole reconnue ; rapproche-toi du micro et réessaie')
        except Exception as exc:
            with self.guard:
                self.state.update(status='cancelled' if self.cancelled else 'error',
                                  error='' if self.cancelled else str(exc) if isinstance(exc, HardwareError) else 'Capture ou transcription micro impossible')
        finally:
            timer.cancel()
            try:
                self._halt(process)
            finally:
                if process.stdout:
                    process.stdout.close()
                with self.guard:
                    self.process = None
                    self.hardware.lock.release()


class Hardware:
    def __init__(self, config):
        self.config = config
        self.settings = config.get('hardware', {})
        self.root = Path(config['data_dir']) / 'hardware'
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.photo_lock = threading.Lock()
        self.model = None
        self.microphone_session = MicrophoneSession(self)
        from .camera import Camera
        self.camera = Camera(self)

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

    def enhanced_photo_path(self, identifier):
        return self.photo_path(identifier).with_name(f'snapshot-{identifier}-enhanced.jpg')

    def prepare_photo(self, identifier):
        with self.photo_lock:
            return self._prepare_photo(identifier)

    def _prepare_photo(self, identifier):
        from .photo_enhancement import enhance_photo
        path = self.photo_path(identifier)
        try:
            original = path.read_bytes()
        except FileNotFoundError as exc:
            raise HardwareError('Photo expirée ; reprendre une capture') from exc
        image, report = enhance_photo(original)
        fd, name = tempfile.mkstemp(dir=self.root, prefix='.enhanced-')
        try:
            with os.fdopen(fd, 'wb') as output:
                output.write(image)
            os.replace(name, self.enhanced_photo_path(identifier))
        finally:
            if os.path.exists(name):
                os.unlink(name)
        return {'image': image, 'image_url': f'/api/hardware/photos/{identifier}/enhanced', 'enhancement': report}

    def capture(self):
        if not shutil.which('ffmpeg'):
            raise HardwareError('ffmpeg absent sur le serveur')
        if not self.lock.acquire(blocking=False):
            raise HardwareBusy('Une capture est déjà en cours')
        identifier = uuid.uuid4().hex
        path = self.photo_path(identifier)
        try:
            size, warnings = self.camera.prepare()
            try:
                command = ['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'v4l2',
                                '-input_format', 'mjpeg', '-video_size', '640x480',
                                '-i', self.status()['camera'], '-vf', 'setpts=PTS-STARTPTS,select=gte(t\\,2)',
                                '-frames:v', '1', '-q:v', '2', '-update', '1', str(path)]
                command[command.index('-video_size') + 1] = size
                try:
                    subprocess.run(command, capture_output=True, check=True, timeout=15)
                except subprocess.SubprocessError:
                    if size != '1280x720':
                        raise
                    size = '640x480'; command[command.index('-video_size') + 1] = size
                    warnings.append('Capture HD refusée ; repli en 640 × 480.')
                    subprocess.run(command, capture_output=True, check=True, timeout=15)
            except (OSError, subprocess.SubprocessError) as exc:
                raise HardwareError('Caméra indisponible ; vérifier /dev/video0 et les droits vidéo') from exc
            if not path.is_file() or not 0 < path.stat().st_size <= 4_000_000:
                raise HardwareError('Image caméra invalide')
            with self.photo_lock:
                photos = sorted((p for p in self.root.glob('snapshot-*.jpg') if re.fullmatch(r'snapshot-[a-f0-9]{32}\.jpg', p.name)),
                                key=lambda p: p.stat().st_mtime, reverse=True)
                for old in photos[3:]:
                    old.with_name(old.stem + '-enhanced.jpg').unlink(missing_ok=True)
                    old.unlink(missing_ok=True)
            width, height = map(int, size.split('x'))
            return {'id': identifier, 'image_url': f'/api/hardware/photos/{identifier}', 'width': width, 'height': height,
                    'warnings': warnings, 'warmup_seconds': 2}
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        finally:
            self.lock.release()
