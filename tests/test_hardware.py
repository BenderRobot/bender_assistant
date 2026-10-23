import asyncio
from io import BytesIO
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from bender_voice.hardware import Hardware, HardwareBusy, HardwareError
from bender_voice.host_player import HostPlayer
from bender_voice.service import VoiceService
from hardware_api import build_hardware_router, get_hardware
from voice_api import get_voice
from test_voice import FakeVoice, wav_file


class HardwareTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.config = {'data_dir': self.temp.name, 'local_provider': 'system', 'system_fallback': True,
                       'lipsync': {'engine': 'acoustic'}, 'elevenlabs': {'enabled': False}}
        self.hardware = Hardware(self.config)
        self.voice = VoiceService(self.config, {name: FakeVoice(name) for name in ('system', 'chatterbox', 'elevenlabs')})

    def tearDown(self):
        self.temp.cleanup()

    def test_control_key_is_persistent_and_required(self):
        token = self.hardware.control_token()
        self.assertGreaterEqual(len(token), 20)
        self.assertEqual(Hardware(self.config).control_token(), token)
        self.assertFalse(self.hardware.authorized(''))
        self.assertTrue(self.hardware.authorized(token))

    def test_microphone_uses_lifecam_and_removes_recording(self):
        (self.hardware.model_dir / 'am').mkdir(parents=True)
        paths = []
        def capture(args, **kwargs):
            self.assertIn('plughw:CARD=HD3000,DEV=0', args)
            self.assertIn('16000', args)
            paths.append(Path(args[-1]));wav_file(paths[-1])
        with patch('shutil.which', return_value='arecord'), patch('subprocess.run', side_effect=capture), patch.object(self.hardware, 'transcribe', return_value='bonjour bender'):
            result = self.hardware.listen(6)
        self.assertEqual(result['text'], 'bonjour bender')
        self.assertFalse(paths[0].exists())
        self.assertFalse(self.hardware.lock.locked())

    def test_missing_model_does_not_record(self):
        with patch('shutil.which', return_value='arecord'), patch('subprocess.run') as command:
            with self.assertRaises(HardwareError):self.hardware.listen(6)
            command.assert_not_called()

    def test_camera_uses_server_device_and_bounds_retention(self):
        def capture(args, **kwargs):
            self.assertIn('/dev/video0', args);self.assertIn('640x480', args)
            Path(args[-1]).write_bytes(b'jpeg-test')
        with patch('shutil.which', return_value='ffmpeg'), patch.object(self.hardware.camera, 'prepare', return_value=('640x480', [])), patch('subprocess.run', side_effect=capture):
            for _ in range(5):result = self.hardware.capture()
        self.assertEqual(len(list(self.hardware.root.glob('snapshot-*.jpg'))), 3)
        self.assertTrue(self.hardware.photo_path(result['id']).exists())
        with self.assertRaises(ValueError):self.hardware.photo_path('../secret')

    def test_capture_lock_and_failure_release(self):
        self.hardware.lock.acquire()
        with patch('shutil.which', return_value='ffmpeg'):
            with self.assertRaises(HardwareBusy):self.hardware.capture()
        self.hardware.lock.release()
        with patch('shutil.which', return_value='ffmpeg'), patch('subprocess.run', side_effect=subprocess.TimeoutExpired('ffmpeg', 12)):
            with self.assertRaises(HardwareError):self.hardware.capture()
        self.assertFalse(self.hardware.lock.locked())
        self.assertFalse(list(self.hardware.root.glob('snapshot-*.jpg')))

    def test_hardware_api_auth_and_vision(self):
        calls = []
        def brain(question, image):
            calls.append((question, image));return 'Je vois un objet.'
        app = FastAPI();app.include_router(build_hardware_router(brain))
        app.dependency_overrides[get_hardware] = lambda: self.hardware
        app.dependency_overrides[get_voice] = lambda: self.voice
        headers = {'X-Bender-Control-Token': self.hardware.control_token()}
        from PIL import Image
        original = BytesIO();Image.new('RGB',(64,48),(160,150,140)).save(original,format='JPEG')
        photo_data=original.getvalue()
        identifier = 'a' * 32;self.hardware.photo_path(identifier).write_bytes(photo_data)
        with TestClient(app) as client:
            for route in ('camera', 'listen', 'play', 'vision', 'stop'):
                self.assertEqual(client.post('/api/hardware/' + route, json={}).status_code, 403)
            self.assertEqual(client.get(f'/api/hardware/photos/{identifier}').status_code, 403)
            photo = client.get(f'/api/hardware/photos/{identifier}', headers=headers)
            self.assertEqual(photo.content, photo_data);self.assertEqual(photo.headers['cache-control'], 'no-store')
            result = client.post('/api/hardware/vision', headers=headers, json={'photo_id': identifier, 'question': 'Que vois-tu ?'})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json()['response'], 'Je vois un objet.')
            self.assertEqual(calls[0][0], 'Que vois-tu ?')
            self.assertNotEqual(calls[0][1], photo_data)
            enhanced=client.get(result.json()['image_url'],headers=headers)
            self.assertEqual(enhanced.content,calls[0][1])
            self.assertEqual(self.hardware.photo_path(identifier).read_bytes(),photo_data)

    def test_host_player_broadcasts_and_returns_to_rest(self):
        from pose_models import EyesShape
        custom = EyesShape(kind='eyes', eyes=[{'cx': x, 'cy': 240, 'rx': 137, 'ry': 130, 'top': [0, 0, 0], 'bottom': [1, 1, 1]} for x in (244, 556)]).model_dump()
        bundle = self.voice.prepare('Bonjour')
        events, ownership = [], []
        class Process:
            returncode = 0
            def __init__(self):self.n = 0
            def poll(self):self.n += 1;return None if self.n < 3 else 0
            def terminate(self):pass
            def wait(self, timeout):return 0
        async def broadcast(event):events.append(event)
        async def scenario():
            player = HostPlayer(self.voice, self.hardware, broadcast, ownership.append)
            with patch('shutil.which', return_value='aplay'), patch('subprocess.Popen', return_value=Process()) as command:
                await player.start([bundle['segments'][0]['id']], custom_eyes=custom);await player.task
                self.assertIn('plughw:CARD=PCH,DEV=0', command.call_args.args[0])
            self.assertEqual(player.state['status'], 'finished')
        asyncio.run(scenario())
        self.assertTrue(any(event['active'] for event in events));self.assertEqual(events[-1]['pose'], 0)
        self.assertEqual(ownership, [True, False])
        self.assertTrue(all(event['custom_eyes'] == custom for event in events))

    def test_stop_before_task_starts_releases_ownership(self):
        bundle = self.voice.prepare('Bonjour');ownership = []
        async def broadcast(event):pass
        async def scenario():
            player = HostPlayer(self.voice, self.hardware, broadcast, ownership.append)
            with patch('shutil.which', return_value='aplay'), patch('subprocess.Popen') as command:
                await player.start([bundle['segments'][0]['id']]);await player.stop();command.assert_not_called()
            self.assertFalse(player.state['active'])
        asyncio.run(scenario());self.assertFalse(ownership[-1])


if __name__ == '__main__':unittest.main()
