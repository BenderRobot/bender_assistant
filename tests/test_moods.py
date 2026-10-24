import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from bender_voice.hardware import Hardware
from bender_voice.moods import MoodScenarios,Scenario,ScenarioConflict,command,reply
from bender_voice.service import VoiceService
from hardware_api import require_control,get_hardware,PlaybackRequest
from mood_api import router,get_moods
from voice_api import get_voice
from test_voice import FakeVoice,wav_file


class MoodTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        self.store=MoodScenarios(self.root)
        self.voice=VoiceService({'data_dir':str(self.root),'local_provider':'system','system_fallback':True,
                                 'lipsync':{'engine':'acoustic'}},
                                {name:FakeVoice(name) for name in ('system','elevenlabs','chatterbox')})
        hardware=Hardware({'data_dir':str(self.root)})
        self.headers={'X-Bender-Control-Token':hardware.control_token()}
        app=FastAPI();app.include_router(router)
        app.dependency_overrides[get_voice]=lambda:self.voice
        app.dependency_overrides[get_moods]=lambda:self.store
        app.dependency_overrides[get_hardware]=lambda:hardware
        self.client=TestClient(app);self.addCleanup(self.client.close)

    def test_explicit_commands_match_mood_and_intensity_without_intercepting_questions(self):
        for text,expected in [('Bender, sois triste',('sad',2)),('Sois un peu sarcastique',('sarcastic',1)),
                              ('sois très joyeux !',('excited',3)),('sois agacé niveau 1',('angry',1)),
                              ('passe en mode calme',('neutral',2)),('sois triste, s’il te plaît',('sad',2))]:
            self.assertEqual(command(text),expected,text)
        for text in ('Pourquoi es-tu triste ?','Ne sois pas triste','Explique « sois triste »','Sois triste et allume la lampe'):
            self.assertIsNone(command(text))

    def test_all_five_moods_have_three_levels_and_random_choices_do_not_repeat_immediately(self):
        self.assertEqual(len(self.store.catalog()['items']),45)
        for mood in ('neutral','sarcastic','angry','excited','sad'):
            for level in (1,2,3):
                values=[self.store.pick(mood,level)['id'] for _ in range(6)]
                self.assertTrue(all(a!=b for a,b in zip(values,values[1:])))
        self.assertTrue(all(provider.calls==0 for provider in self.voice.providers.values()))

    def test_saved_custom_eyes_survive_restart_and_stale_edit_is_rejected(self):
        from pose_models import EyesShape
        data=self.store.catalog();item=data['items'][0]
        item['custom_eyes']=EyesShape(kind='eyes',eyes=[dict(cx=x,cy=240,rx=137,ry=130,top=[0.2,0.3,0.2],bottom=[1,1,1]) for x in (244,556)]).model_dump()
        saved=self.store.save(Scenario.model_validate(item),data['revision'])
        self.assertEqual(MoodScenarios(self.root).catalog(),saved)
        with self.assertRaises(ScenarioConflict):self.store.save(Scenario.model_validate(item),data['revision'])
        copy=self.store.save(Scenario.model_validate(item),saved['revision'],True)
        self.assertEqual(len(copy['items']),46)

    def test_response_eyes_are_playback_metadata_and_never_modify_shared_audio(self):
        result=reply(self.store,self.voice,'sad',3,'auto')
        segment=result['speech']['segments'][0]
        self.assertEqual(segment['face_override']['eyes'],'crying')
        self.assertEqual(result['timings']['brain_source'],'local')
        metadata=json.loads(self.voice.asset(segment['id'],'json').read_text(encoding='utf-8'))
        self.assertEqual(metadata['eyes'],'normal');self.assertNotIn('face_override',metadata)
        self.assertEqual(result['mood_scenario']['intensity'],3)
        self.assertEqual(self.voice.providers['elevenlabs'].calls,0)

    def test_recorded_reply_uses_its_real_words_without_new_synthesis(self):
        wav_file(self.root/'library'/'recording.wav')
        (self.root/'library/catalog.json').write_text(json.dumps([dict(id='recording',audio='recording.wav',text='Texte réellement enregistré',enabled=True)]),encoding='utf-8')
        data=self.store.catalog()
        for item in data['items']:
            if item['mood']=='sad' and item['intensity']==2:
                item['library_id']='recording'
                self.store.save(Scenario.model_validate(item),self.store.catalog()['revision'])
        result=reply(self.store,self.voice,'sad',2)
        self.assertEqual(result['response'],'Texte réellement enregistré')
        self.assertEqual(result['speech']['segments'][0]['source'],'library')
        self.assertTrue(all(provider.calls==0 for provider in self.voice.providers.values()))

    def test_owner_control_and_invalid_eye_geometry_are_enforced(self):
        self.assertEqual(self.client.get('/api/moods').status_code,403)
        self.assertEqual(self.client.post('/api/moods/prepare',json={'mood':'sad'}).status_code,403)
        data=self.client.get('/api/moods',headers=self.headers).json()
        body={'revision':data['revision'],'scenario':data['items'][0]}
        body['scenario']['custom_eyes']={'kind':'eyes','eyes':[]}
        self.assertEqual(self.client.post('/api/moods',headers=self.headers,json=body).status_code,422)
        response=self.client.post('/api/moods/prepare',headers=self.headers,json={'mood':'sad','intensity':1,'speech':False})
        self.assertEqual(response.status_code,200);self.assertNotIn('speech',response.json())
        self.assertTrue(all(provider.calls==0 for provider in self.voice.providers.values()))
        with self.assertRaises(ValidationError):PlaybackRequest(ids=['a'],faces=[])

    def test_disabled_pool_returns_an_error_instead_of_an_unrelated_scenario(self):
        for item in self.store.catalog()['items']:
            if item['mood']=='sad' and item['intensity']==1:
                item['enabled']=False;self.store.save(Scenario.model_validate(item),self.store.catalog()['revision'])
        with self.assertRaisesRegex(ValueError,'Aucun scénario'):self.store.pick('sad',1)

    def test_chat_command_uses_scenarios_without_gpt(self):
        import memory
        with patch.object(memory,'DB_PATH',str(self.root/'old-memory.db')):
            import server
        previous=dict(server.app.dependency_overrides)
        try:
            server.app.dependency_overrides[require_control]=lambda:None
            with TestClient(server.app) as client,patch('server.get_moods',return_value=self.store),patch('server.get_voice',return_value=self.voice),patch('server.process_command') as brain:
                result=client.post('/api/chat',json={'message':'Sois triste niveau 3','speech':False}).json()
                self.assertEqual(result['mood_scenario']['eyes'],'crying');brain.assert_not_called()
        finally:
            server.app.dependency_overrides.clear();server.app.dependency_overrides.update(previous)

    def test_mood_editor_controller(self):
        import shutil,subprocess
        if not shutil.which('node'):self.skipTest('Node facultatif pour les tests web')
        result=subprocess.run([shutil.which('node'),str(Path(__file__).with_name('mood-scenarios-ui.cjs'))],
                              capture_output=True,text=True,encoding='utf-8',timeout=15)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
