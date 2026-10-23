import io
import subprocess
import tempfile
import threading
import unittest
import wave
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from bender_voice.hardware import Hardware, HardwareBusy, HardwareError
from bender_voice.service import VoiceService
from hardware_api import build_hardware_router, get_hardware
from voice_api import get_voice
from test_voice import FakeVoice


class Capture:
    """ALSA-like process which emits PCM and keeps recording until terminated."""
    def __init__(self):
        self.done = threading.Event()
        self.returncode = None
        self.first = True
        self.stdout = self
        self.closed = False

    def read(self, size):
        if self.first:
            self.first = False
            return b'\0' * 3200
        if not self.done.wait(3):
            raise RuntimeError('Test capture was not stopped')
        return b''

    def poll(self): return self.returncode
    def terminate(self): self.returncode = -15; self.done.set()
    def kill(self): self.returncode = -9; self.done.set()
    def wait(self, timeout=None):
        if not self.done.wait(timeout): raise subprocess.TimeoutExpired('arecord', timeout)
        return self.returncode
    def close(self): self.closed = True


class NaturalCapture:
    returncode = 0
    def __init__(self): self.stdout = io.BytesIO(b'\0' * 64000)
    def poll(self): return 0
    def wait(self, timeout=None): return 0
    def terminate(self): raise AssertionError('Already exited')


class MicrophoneTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.config = {'data_dir': self.temp.name, 'local_provider': 'system', 'system_fallback': True,
                       'lipsync': {'engine': 'acoustic'}, 'elevenlabs': {'enabled': False}}
        self.hardware = Hardware(self.config)
        (self.hardware.model_dir / 'am').mkdir(parents=True)
        self.session = self.hardware.microphone_session
        self.voice = VoiceService(self.config, {name: FakeVoice(name) for name in ('system','chatterbox','elevenlabs')})

    def tearDown(self):
        state = self.session.snapshot()
        if state['status'] in self.session.ACTIVE:
            self.session.stop(state['session_id'], cancel=True)
        if self.session.thread:
            self.session.thread.join(4)
        self.temp.cleanup()

    def test_pause_finalizes_wav_transcribes_and_releases_device(self):
        process = Capture(); paths = []
        def transcribe(path):
            paths.append(path)
            with wave.open(str(path), 'rb') as wav:
                self.assertEqual((wav.getnchannels(), wav.getframerate(), wav.getsampwidth()), (1,16000,2))
                self.assertEqual(wav.getnframes(), 1600)
            return 'allume la lumière'
        with patch('shutil.which', return_value='arecord'), patch('subprocess.Popen', return_value=process) as spawn, patch.object(self.hardware, 'transcribe', side_effect=transcribe):
            state = self.session.start(60)
            self.assertTrue(self.hardware.lock.locked())
            self.session.stop(state['session_id'])
            self.session.thread.join(3)
            result = self.session.snapshot(state['session_id'])
        self.assertEqual(result['status'], 'finished'); self.assertEqual(result['text'], 'allume la lumière')
        self.assertEqual(result['stop_reason'], 'manual')
        self.assertIn('raw', spawn.call_args.args[0]); self.assertIn('plughw:CARD=HD3000,DEV=0', spawn.call_args.args[0])
        self.assertFalse(self.hardware.lock.locked()); self.assertTrue(process.closed)
        self.assertFalse(paths[0].exists())

    def test_cancel_does_not_transcribe_or_keep_audio(self):
        with patch('shutil.which', return_value='arecord'), patch('subprocess.Popen', return_value=Capture()), patch.object(self.hardware, 'transcribe') as transcribe:
            state = self.session.start()
            self.session.stop(state['session_id'], cancel=True); self.session.thread.join(3)
            self.assertEqual(self.session.snapshot()['status'], 'cancelled')
            transcribe.assert_not_called()
        self.assertFalse(list(self.hardware.root.glob('tmp*')))

    def test_auto_limit_finishes_and_new_session_has_new_id(self):
        with patch('shutil.which', return_value='arecord'), patch('subprocess.Popen', side_effect=lambda *a, **k: NaturalCapture()), patch.object(self.hardware, 'transcribe', return_value='bonjour'):
            first = self.session.start(2); self.session.thread.join(3)
            self.assertEqual(self.session.snapshot()['stop_reason'], 'limit')
            self.assertEqual(self.session.snapshot()['text'], 'bonjour')
            second = self.session.start(2); self.session.thread.join(3)
            self.assertNotEqual(first['session_id'], second['session_id'])
            with self.assertRaises(ValueError): self.session.stop(first['session_id'])

    def test_device_lock_prevents_parallel_recording_and_camera(self):
        with patch('shutil.which', return_value='arecord'), patch('subprocess.Popen', return_value=Capture()):
            state = self.session.start()
            with self.assertRaises(HardwareBusy): self.session.start()
            with self.assertRaises(HardwareBusy): self.hardware.listen()
            with self.assertRaises(HardwareBusy): self.hardware.capture()
            with self.assertRaises(ValueError): self.session.stop('a'*32)
            self.assertEqual(self.session.snapshot()['status'], 'recording')
            self.session.stop(state['session_id'], cancel=True); self.session.thread.join(3)

    def test_spawn_and_transcription_errors_release_the_microphone(self):
        with patch('shutil.which', return_value='arecord'), patch('subprocess.Popen', side_effect=OSError()):
            with self.assertRaises(HardwareError): self.session.start()
            self.assertFalse(self.hardware.lock.locked())
        with patch('shutil.which', return_value='arecord'), patch('subprocess.Popen', return_value=NaturalCapture()), patch.object(self.hardware, 'transcribe', side_effect=HardwareError('Modèle Vosk invalide')):
            self.session.start(2); self.session.thread.join(3)
            self.assertEqual(self.session.snapshot()['error'], 'Modèle Vosk invalide')
            self.assertEqual(self.session.snapshot()['status'], 'error')
            self.assertFalse(self.hardware.lock.locked())

    def test_api_auth_stop_and_status_do_not_call_the_brain(self):
        calls = []
        app = FastAPI(); app.include_router(build_hardware_router(lambda *args: calls.append(args)))
        app.dependency_overrides[get_hardware] = lambda: self.hardware
        app.dependency_overrides[get_voice] = lambda: self.voice
        headers = {'X-Bender-Control-Token': self.hardware.control_token()}
        with TestClient(app) as client, patch('shutil.which', return_value='arecord'), patch('subprocess.Popen', return_value=Capture()), patch.object(self.hardware, 'transcribe', return_value='que vois tu'):
            self.assertEqual(client.post('/api/hardware/listen/start', json={}).status_code, 403)
            self.assertEqual(client.post('/api/hardware/listen/stop', json={}).status_code, 403)
            self.assertEqual(client.get('/api/hardware/listen/status').status_code, 403)
            self.assertEqual(client.post('/api/hardware/listen/start', headers=headers, json={'max_seconds':61}).status_code, 422)
            start = client.post('/api/hardware/listen/start', headers=headers, json={})
            self.assertEqual(start.status_code, 200); identifier = start.json()['session_id']
            self.assertEqual(client.post('/api/hardware/play', headers=headers, json={'ids':['x']}).status_code, 409)
            self.assertEqual(client.post('/api/hardware/listen/stop', headers=headers, json={'session_id':'f'*32}).status_code, 409)
            self.assertEqual(client.post('/api/hardware/listen/stop', headers=headers, json={'session_id':identifier}).status_code, 200)
            self.session.thread.join(3)
            result = client.get('/api/hardware/listen/status', headers=headers, params={'session_id':identifier})
            self.assertEqual(result.json()['text'], 'que vois tu')
            self.assertEqual(client.get('/api/hardware/listen/status', headers=headers, params={'session_id':'f'*32}).status_code, 404)
        self.assertEqual(calls, [])  # The browser submits the visible transcript separately.
