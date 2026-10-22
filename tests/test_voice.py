import copy
import json
import math
import shutil
import struct
import tempfile
import unittest
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from bender_voice.config import inside
from bender_voice.lipsync import validate_timeline
from bender_voice.providers import VoiceUnavailable
from bender_voice.service import VoiceService
from voice_api import get_voice, router


def wav_file(path):
    with wave.open(str(path), 'wb') as wav:
        wav.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
        wav.writeframes(b''.join(struct.pack('<h', int(8000 * math.sin(i / 10))) for i in range(12000)))


class FakeVoice:
    def __init__(self, name, fail=False):
        self.name, self.fail, self.calls, self.version = name, fail, 0, 1

    def identity(self, mood):
        return {'provider': self.name, 'version': self.version, 'mood': mood}

    def available(self):
        return True

    def synthesize(self, text, mood, target):
        self.calls += 1
        if self.fail:
            raise VoiceUnavailable('Moteur de test indisponible')
        wav_file(target)


class VoiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.config = {'data_dir': self.temp.name, 'local_provider': 'chatterbox', 'system_fallback': True,
                       'lipsync': {'engine': 'acoustic'}, 'elevenlabs': {'enabled': True, 'daily_character_limit': 100},
                       'quotes': {'probability': 1, 'global_cooldown_seconds': 0}}
        self.providers = {name: FakeVoice(name) for name in ('chatterbox', 'elevenlabs', 'system')}
        self.service = VoiceService(self.config, self.providers)

    def tearDown(self):
        self.temp.cleanup()

    def test_cached_cloud_does_not_spend_again(self):
        first = self.service.prepare('Bonjour', mode='cloud')
        second = self.service.prepare('Bonjour')
        self.assertEqual(first['segments'][0]['id'], second['segments'][0]['id'])
        self.assertTrue(second['segments'][0]['cached'])
        self.assertEqual(self.providers['elevenlabs'].calls, 1)
        self.assertEqual(self.service.store.usage()['characters_reserved'], 7)

    def test_budget_survives_restart_and_falls_back(self):
        self.config['elevenlabs']['daily_character_limit'] = 7
        self.service.prepare('Bonjour', mode='cloud')
        other = VoiceService(self.config, self.providers)
        result = other.prepare('Un autre texte', mode='cloud')
        self.assertEqual(result['segments'][0]['source'], 'chatterbox')
        self.assertEqual(self.providers['elevenlabs'].calls, 1)
        self.assertIn('Plafond', result['warnings'][0])

    def test_cloud_failure_is_not_retried(self):
        self.providers['elevenlabs'].fail = True
        result = self.service.prepare('Bonjour', mode='cloud')
        self.assertEqual(result['segments'][0]['source'], 'chatterbox')
        self.assertEqual(self.providers['elevenlabs'].calls, 1)
        self.assertEqual(self.service.store.usage()['characters_reserved'], 7)

    def test_monthly_limit_prevents_cloud(self):
        self.config['elevenlabs']['monthly_character_limit'] = 1
        result = self.service.prepare('Bonjour', mode='cloud')
        self.assertEqual(result['segments'][0]['source'], 'chatterbox')
        self.assertEqual(self.providers['elevenlabs'].calls, 0)

    def test_local_mode_never_uses_cloud(self):
        self.service.prepare('Bonjour', mode='local', topic='news')
        self.assertEqual(self.providers['elevenlabs'].calls, 0)

    def test_changed_voice_invalidates_cache(self):
        first = self.service.prepare('Bonjour', mode='local')
        self.providers['chatterbox'].version = 2
        second = self.service.prepare('Bonjour', mode='local')
        self.assertNotEqual(first['segments'][0]['id'], second['segments'][0]['id'])

    def test_same_parallel_request_only_generates_once(self):
        with ThreadPoolExecutor(2) as pool:
            list(pool.map(lambda _: self.service.prepare('Bonjour'), range(2)))
        self.assertEqual(self.providers['chatterbox'].calls, 1)

    def test_library_basic_must_match_the_response(self):
        if not shutil.which('ffmpeg'):
            self.skipTest('ffmpeg absent')
        source = Path(self.temp.name) / 'source.wav';wav_file(source)
        self.service.register(source, 'allume', "OK j'allume la lumière", kind='basic')
        wrong = self.service.prepare("Je n'ai pas pu allumer la lumière")
        self.assertNotEqual(wrong['segments'][0]['source'], 'library')
        correct = self.service.prepare("OK j'allume la lumière", mode='cache')
        self.assertEqual(correct['segments'][0]['source'], 'library')

    def test_quotes_match_words_and_obey_cooldown(self):
        if not shutil.which('ffmpeg'):
            self.skipTest('ffmpeg absent')
        source = Path(self.temp.name) / 'source.wav';wav_file(source)
        self.service.register(source, 'salon', 'Réplique test', triggers=['salon'])
        no_match = self.service.prepare('Bonjour', context='salonique', allow_quote=True)
        self.assertEqual(len(no_match['segments']), 1)
        yes = self.service.prepare('Bonjour', context='lumière salon', allow_quote=True)
        self.assertEqual(len(yes['segments']), 2)
        repeat = self.service.prepare('Bonjour', context='salon', allow_quote=True)
        self.assertEqual(len(repeat['segments']), 1)

    def test_paths_and_timelines_rejected(self):
        with self.assertRaises(ValueError): inside(self.temp.name, '../escape.wav')
        for cues in ([{'t': -1, 'pose': 0}], [{'t': 0, 'pose': 99}], [{'t': 0, 'pose': True}], [{'t': float('nan'), 'pose': 0}]):
            with self.assertRaises(ValueError): validate_timeline({'cues': cues}, 1)

    def test_api_assets_and_schema(self):
        app = FastAPI();app.include_router(router);app.dependency_overrides[get_voice] = lambda: self.service
        with TestClient(app) as client:
            response = client.post('/api/speech', json={'text': 'Bonjour'})
            self.assertEqual(response.status_code, 200)
            segment = response.json()['segments'][0]
            self.assertEqual(client.get(segment['audio_url']).status_code, 200)
            timeline = client.get(segment['timeline_url']).json()
            self.assertEqual(timeline['cues'][-1]['pose'], 0)
            self.assertEqual(client.post('/api/speech', json={'text': 'x', 'mode': 'bad'}).status_code, 422)
            self.assertEqual(client.get('/api/voice/assets/not-a-hash.wav').status_code, 404)

    def test_face_broadcast(self):
        app = FastAPI();app.include_router(router)
        with TestClient(app) as client:
            with client.websocket_connect('/api/face') as a, client.websocket_connect('/api/face') as b:
                state = {'pose': 11, 'active': True, 'eyes': 'ref3'}
                a.send_json(state)
                received = b.receive_json()
                self.assertEqual(received['pose'], 11)
                self.assertEqual(received['eyes'], 'ref3')


if __name__ == '__main__':
    unittest.main()
