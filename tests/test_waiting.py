import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from bender_voice.hardware import Hardware
from bender_voice.service import VoiceService
from bender_voice import waiting
from hardware_api import get_hardware
from voice_api import get_voice
from waiting_api import router
from test_voice import FakeVoice


class WaitingTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.config={'data_dir':temporary.name,'local_provider':'chatterbox','lipsync':{'engine':'acoustic'},
                     'elevenlabs':{'enabled':True,'daily_character_limit':2000}}
        self.providers={name:FakeVoice(name) for name in ('elevenlabs','chatterbox','system')}
        self.voice=VoiceService(self.config,self.providers)
        hardware=Hardware(self.config)
        self.headers={'X-Bender-Control-Token':hardware.control_token()}
        app=FastAPI();app.include_router(router)
        app.dependency_overrides[get_voice]=lambda:self.voice
        app.dependency_overrides[get_hardware]=lambda:hardware
        self.client=TestClient(app)
        self.addCleanup(self.client.close)

    def test_empty_catalogue_and_conversation_never_generate_an_acknowledgement(self):
        status=self.client.get('/api/voice/waiting').json()
        self.assertEqual(status['ready'],0)
        self.assertEqual(status['missing_characters'],sum(map(len,waiting.PHRASES)))
        result=self.client.post('/api/chat/acknowledgement',headers=self.headers,json={'message':'Explique-moi la gravité'}).json()
        self.assertIsNone(result['segment'])
        self.assertTrue(all(provider.calls==0 for provider in self.providers.values()))

    def test_prepare_requires_control_and_reuses_matching_voice_cache(self):
        self.assertEqual(self.client.post('/api/voice/waiting/prepare').status_code,403)
        self.assertEqual(self.providers['elevenlabs'].calls,0)
        first=self.client.post('/api/voice/waiting/prepare',headers=self.headers).json()
        second=self.client.post('/api/voice/waiting/prepare',headers=self.headers).json()
        self.assertEqual(first['ready'],len(waiting.PHRASES))
        self.assertEqual(second['missing_characters'],0)
        self.assertEqual(self.providers['elevenlabs'].calls,len(waiting.PHRASES))
        self.assertEqual(self.providers['chatterbox'].calls,0)
        self.assertEqual(self.providers['system'].calls,0)
        self.assertEqual(self.voice.store.usage()['characters_reserved'],sum(map(len,waiting.PHRASES)))
        response=self.client.post('/api/chat/acknowledgement',headers=self.headers,json={'message':'Explique-moi la gravité'}).json()
        item=response['segment'];self.assertTrue(item['cached']);self.assertEqual(item['source'],'elevenlabs')
        other=self.client.post('/api/chat/acknowledgement',headers=self.headers,
                               json={'message':'Une autre question','previous':item['id']}).json()
        self.assertNotEqual(other['segment']['id'],item['id'])
        self.assertEqual(self.providers['elevenlabs'].calls,len(waiting.PHRASES))
        self.providers['elevenlabs'].version+=1
        self.assertEqual(self.client.get('/api/voice/waiting').json()['ready'],0)

    def test_no_waiting_for_local_mode_or_greetings_and_no_slow_fallback(self):
        waiting.prepare(self.voice)
        for payload in ({'message':'salut'},{'message':'une question','mode':'local'}):
            self.assertIsNone(self.client.post('/api/chat/acknowledgement',headers=self.headers,json=payload).json()['segment'])
        self.providers['elevenlabs'].version+=1;self.providers['elevenlabs'].fail=True
        self.assertEqual(self.client.post('/api/voice/waiting/prepare',headers=self.headers).status_code,503)
        self.assertEqual(self.providers['chatterbox'].calls,0)
        self.assertEqual(self.providers['system'].calls,0)

    def test_catalogue_read_does_not_wait_for_an_in_progress_synthesis_lock(self):
        import threading
        result=[]
        with self.voice.lock:
            reader=threading.Thread(target=lambda:result.append(waiting.catalogue(self.voice)))
            reader.start();reader.join(timeout=1)
            self.assertFalse(reader.is_alive())
        self.assertEqual(result[0]['ready'],0)
