import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from bender_media.catalog import Catalog
from bender_media.versions import overview
from bender_voice.hardware import Hardware
from bender_voice.service import VoiceService
from hardware_api import get_hardware
from media_api import build_media_router, get_media, get_media_worker
from voice_api import get_voice
from test_voice import FakeVoice, wav_file


class MediaVersionTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        self.catalog=Catalog(self.root/'media')
        self.voice=VoiceService({'data_dir':str(self.root/'voice')},
                               {name:FakeVoice(name) for name in ('system','elevenlabs','chatterbox')})
        self.identifier='a'*64
        self.catalog.add(self.identifier,'source.mp4','.mp4')
        self.audio=self.voice.store.root/'library'/'clip.wav';wav_file(self.audio)
        self.library=[dict(id='quote-one',type='quote',audio='clip.wav',enabled=True,text='Bonne question')]
        self.save_library()
        self.reference='references/neutral.wav';wav_file(self.voice.store.root/self.reference)
        self.voice.config['reference_by_mood']={'neutral':self.reference}
        self.frame=self.catalog.derived(self.identifier)/'frame-0.jpg';self.frame.write_bytes(b'test-image')
        self.selections=[
            dict(selection_id='1'*16,use='quote',mood='sarcastic',title='Bonne question',text='Bonne question',
                 start=0,end=0.5,triggers=['question'],library_id='quote-one'),
            dict(selection_id='2'*16,use='voice_reference',mood='neutral',title='Voix neutre',text='Bonjour',
                 start=0,end=4,reference_file=self.reference),
            dict(selection_id='3'*16,use='expression',mood='excited',title='Bouche ouverte',start=1,end=2),
        ]
        self.save_selections()
        hardware=Hardware({'data_dir':str(self.root/'voice')})
        self.headers={'X-Bender-Control-Token':hardware.control_token()}
        worker=Mock();worker.status.return_value={'automatic':False,'active':False}
        app=FastAPI();app.include_router(build_media_router())
        app.dependency_overrides[get_hardware]=lambda:hardware
        app.dependency_overrides[get_media]=lambda:self.catalog
        app.dependency_overrides[get_voice]=lambda:self.voice
        app.dependency_overrides[get_media_worker]=lambda:worker
        self.client=TestClient(app);self.addCleanup(self.client.close)

    def save_library(self):
        (self.voice.store.root/'library/catalog.json').write_text(json.dumps(self.library),encoding='utf-8')

    def save_selections(self):
        self.catalog.update(self.identifier,state='approved',media={'frames':[{'index':0,'time':1.5}]},
                            approved=self.selections)

    def test_versions_show_only_approved_usable_assets_without_generating(self):
        data=overview(self.catalog,self.voice)
        self.assertEqual(len(data['moods']),5)
        self.assertEqual(data['total'],3);self.assertEqual(data['ready_quotes'],1)
        by_use={item['use']:item for item in data['selections']}
        self.assertTrue(by_use['voice_reference']['active'])
        self.assertFalse(by_use['voice_reference']['ready_for_response'])
        self.assertTrue(by_use['expression']['available'])
        self.assertFalse(by_use['expression']['ready_for_response'])
        self.assertIsNone(by_use['expression']['audio_url'])
        self.assertNotIn(str(self.root),json.dumps(data))
        self.assertTrue(all(provider.calls==0 for provider in self.voice.providers.values()))
        self.assertEqual(self.voice.store.usage()['characters_reserved'],0)

    def test_missing_disabled_and_unassigned_references_are_not_claimed_ready(self):
        self.library[0]['enabled']=False;self.save_library()
        self.voice.config['reference_by_mood']={'sad':self.reference}
        self.frame.unlink()
        data=overview(self.catalog,self.voice)
        self.assertEqual(data['ready_quotes'],0)
        by_use={item['use']:item for item in data['selections']}
        self.assertFalse(by_use['voice_reference']['active'],'A fallback reference does not fill another mood')
        self.assertFalse(by_use['expression']['available'])
        self.audio.unlink();(self.voice.store.root/self.reference).unlink()
        data=overview(self.catalog,self.voice)
        self.assertTrue(all(not item['available'] for item in data['selections']))

    def test_protected_preview_returns_the_validated_clip_and_never_the_full_source(self):
        url=f'/api/media/{self.identifier}/selections/{"1"*16}/audio'
        self.assertEqual(self.client.get('/api/media/versions').status_code,403)
        self.assertEqual(self.client.get(url).status_code,403)
        result=self.client.get(url,headers=self.headers)
        self.assertEqual(result.status_code,200)
        self.assertEqual(result.content,self.audio.read_bytes())
        self.assertEqual(result.headers['cache-control'],'no-store')
        self.assertEqual(self.client.get(url.replace('1'*16,'9'*16),headers=self.headers).status_code,404)
        self.assertEqual(self.client.get(url.replace('1'*16,'3'*16),headers=self.headers).status_code,404)
        self.assertEqual(self.client.get('/api/media',headers=self.headers).json()['versions']['ready_quotes'],1)
        self.assertTrue(all(provider.calls==0 for provider in self.voice.providers.values()))

    def test_invalid_reference_paths_never_expose_private_or_outside_files(self):
        self.selections[1]['reference_file']='../outside.wav';self.save_selections()
        data=overview(self.catalog,self.voice)
        item=next(item for item in data['selections'] if item['use']=='voice_reference')
        self.assertFalse(item['available']);self.assertIsNone(item['audio_url'])
        url=f'/api/media/{self.identifier}/selections/{"2"*16}/audio'
        self.assertEqual(self.client.get(url,headers=self.headers).status_code,404)
        self.selections[1]['reference_file']='library/clip.wav';self.save_selections()
        self.assertEqual(self.client.get(url,headers=self.headers).status_code,404)

    def test_incomplete_library_during_publication_keeps_other_references_visible(self):
        (self.voice.store.root/'library/catalog.json').write_text('[',encoding='utf-8')
        data=overview(self.catalog,self.voice)
        self.assertEqual(data['ready_quotes'],0);self.assertTrue(data['warnings'])
        reference=next(item for item in data['selections'] if item['use']=='voice_reference')
        self.assertTrue(reference['available']);self.assertTrue(reference['active'])

    @unittest.skipUnless(shutil.which('node'),'Node facultatif pour tester les versions web')
    def test_versions_web_filters_preview_activation_and_mouth_playback(self):
        import subprocess
        result=subprocess.run([shutil.which('node'),str(Path(__file__).with_name('media-versions-ui.cjs'))],
                              capture_output=True,text=True,encoding='utf-8',timeout=15)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
