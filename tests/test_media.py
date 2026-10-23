from io import BytesIO
import json
from pathlib import Path
import shutil
import tarfile
import tempfile
import unittest
from unittest.mock import Mock, patch
import wave

from fastapi import FastAPI
from fastapi.testclient import TestClient

from bender_media.catalog import Catalog, digest_file
from bender_media.transfer import pack, install
from bender_media.analysis import analyze
from bender_media.processing import prepare
from bender_media.worker import Worker
from bender_brain import BrainError
from bender_brain.client import Client
from bender_voice.hardware import Hardware
from bender_voice.service import VoiceService
from media_api import build_media_router, get_media, get_media_worker, Approval, approve
from hardware_api import get_hardware
from voice_api import get_voice
from test_brain import Reply
from test_voice import FakeVoice


def wav(path,seconds=4):
    with wave.open(str(path),'wb') as output:
        output.setnchannels(1);output.setsampwidth(2);output.setframerate(16000)
        output.writeframes(b'\0\x10'*int(16000*seconds))


def report():
    return dict(title='Bonjour sarcastique',summary='Une courte réplique.',mood='sarcastic',categories=['salutation'],
                triggers=['bonjour'],segments=[dict(start=0,end=1,text='bonjour',use='quote',reason='Réponse courte.')],
                expressions=[],warnings=['Humeur supposée à partir du texte ; écouter la voix.'])


def client_for(value=None):
    auth=Mock();auth.status.return_value={'authorized':True}
    auth.credential.return_value=('account-test',dict(model='available-model',access_token='private-test-access'))
    http=Mock()
    text=json.dumps(value if value is not None else report())
    http.request.side_effect=lambda *args,**kwargs:Reply(events=[dict(type='response.output_text.delta',delta=text),dict(type='response.completed')])
    return Client(auth,http)


class MediaTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.inbox=self.root/'inbox';self.inbox.mkdir()
        self.catalog=Catalog(self.root/'server-media')
        self.hardware=Hardware({'data_dir':str(self.root/'voice')})
        self.voice=VoiceService({'data_dir':str(self.root/'voice'),'lipsync':{'engine':'acoustic'}},
                               {name:FakeVoice(name) for name in ('system','chatterbox','elevenlabs')})

    def tearDown(self):self.temp.cleanup()

    def imported(self):
        path=self.inbox/'bonjour.wav';wav(path)
        archive=self.root/'media.tar.gz';self.assertEqual(pack(self.inbox,archive),1)
        self.assertEqual(install(archive,self.catalog),1)
        return digest_file(path)

    def prepared(self):
        identifier=self.imported();directory=self.catalog.derived(identifier);wav(directory/'audio.wav')
        self.catalog.update(identifier,media=dict(duration=4,audio='audio.wav',frames=[],transcript='bonjour',words=[],transcribed=True,metrics={}))
        return identifier

    def test_incremental_transfer_deduplicates_content_even_after_rename(self):
        identifier=self.imported()
        shutil.copyfile(self.inbox/'bonjour.wav',self.inbox/'same-renamed.wav')
        self.assertEqual(pack(self.inbox,self.root/'empty.tar.gz',self.catalog.inventory()),0)
        self.assertEqual(len(self.catalog.list()),1)
        self.assertEqual(install(self.root/'media.tar.gz',self.catalog),0)
        self.assertEqual(self.catalog.original(identifier).read_bytes(),(self.inbox/'bonjour.wav').read_bytes())

    def test_archive_path_links_and_wrong_hash_are_rejected_without_import(self):
        for name,kind in [('../escape.wav',tarfile.REGTYPE),('a'*64+'.wav',tarfile.SYMTYPE)]:
            archive=self.root/'malicious.tar.gz'
            with tarfile.open(archive,'w:gz') as bundle:
                item=tarfile.TarInfo(name);item.type=kind;item.linkname='../other';bundle.addfile(item,BytesIO())
            with self.assertRaises(ValueError):install(archive,self.catalog)
        path=self.inbox/'bonjour.wav';wav(path);identifier=digest_file(path)
        entries=[dict(id=identifier,name='bonjour.wav',extension='.wav',size=4)]
        with tarfile.open(self.root/'wrong.tar.gz','w:gz') as bundle:
            for name,data in [('manifest.json',json.dumps(entries).encode()),(identifier+'.wav',b'fake')]:
                item=tarfile.TarInfo(name);item.size=len(data);bundle.addfile(item,BytesIO(data))
        with self.assertRaises(ValueError):install(self.root/'wrong.tar.gz',self.catalog)
        self.assertEqual(self.catalog.list(),[])

    def test_worker_analyzes_only_new_samples_and_never_promotes_automatically(self):
        identifier=self.prepared();client=client_for()
        worker=Worker(self.catalog,self.hardware,client);worker.run()
        result=self.catalog.get(identifier)
        self.assertEqual(result['state'],'review');self.assertEqual(result['analysis']['title'],'Bonjour sarcastique')
        self.assertEqual(result['approved'],[]);self.assertEqual(self.voice.store.library(),[])
        worker.run();self.assertEqual(client.http.request.call_count,1)
        payload=client.http.request.call_args.kwargs['json']
        self.assertFalse(payload['store']);self.assertTrue(payload['stream'])
        self.assertNotIn('previous_response_id',payload);self.assertNotIn('temperature',payload)

    def test_unconnected_or_paused_worker_keeps_new_media_pending(self):
        identifier=self.imported();client=client_for();client.auth.status.return_value={'authorized':False}
        worker=Worker(self.catalog,self.hardware,client)
        with patch('bender_media.worker.prepare') as conversion:
            worker.run();conversion.assert_not_called()
        self.assertEqual(self.catalog.get(identifier)['state'],'pending')
        self.catalog.automatic(False);client.auth.status.return_value={'authorized':True}
        worker.run();client.http.request.assert_not_called()

    def test_bad_model_output_or_outside_intervals_is_not_approved(self):
        identifier=self.prepared();data=report();data['segments'][0]['end']=10
        worker=Worker(self.catalog,self.hardware,client_for(data));worker.run()
        self.assertEqual(self.catalog.get(identifier)['state'],'error')
        self.assertEqual(self.catalog.get(identifier)['analysis'],{})

    def test_visual_analysis_uses_timestamped_images_without_audio_upload(self):
        identifier=self.prepared();media=self.catalog.get(identifier)['media']
        (self.catalog.derived(identifier)/'frame-0.jpg').write_bytes(b'jpeg-test')
        media['frames']=[dict(index=0,time=1,file='frame-0.jpg')];self.catalog.update(identifier,media=media)
        client=client_for();analyze(client,self.catalog,self.catalog.get(identifier))
        inputs=client.http.request.call_args.kwargs['json']['input'][0]['content']
        self.assertEqual([item['type'] for item in inputs],['input_text','input_text','input_image'])
        self.assertTrue(inputs[-1]['image_url'].startswith('data:image/jpeg;base64,'))

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg requis pour le test réel de conversion')
    def test_local_audio_preparation_and_reviewed_quote_reference_exports(self):
        identifier=self.imported();media=prepare(self.catalog,identifier)
        self.assertAlmostEqual(media['duration'],4,places=2);self.assertEqual(media['frames'],[])
        self.assertIn('rms_dbfs',media['metrics'])
        self.catalog.update(identifier,state='review',media={**media,'transcript':'bonjour'})
        selection=Approval(use='quote',start=0,end=1,text='Bonjour.',title='Salut',triggers=['bonjour'])
        with self.assertRaises(ValueError):approve(self.catalog,identifier,selection,self.voice)
        selection.bender_only=True;entry=approve(self.catalog,identifier,selection,self.voice)
        again=approve(self.catalog,identifier,selection,self.voice)
        self.assertEqual(entry,again);self.assertEqual(len(self.voice.store.library()),1)
        with wave.open(str(self.voice.store.root/'library'/(entry['library_id']+'.wav')),'rb') as audio:
            self.assertAlmostEqual(audio.getnframes()/audio.getframerate(),1,places=2)
        reference=Approval(use='voice_reference',start=0,end=3,text='Bonjour',title='Voix neutre',bender_only=True)
        result=approve(self.catalog,identifier,reference,self.voice)
        self.assertTrue((self.voice.store.root/result['reference_file']).is_file())
        self.assertNotIn('reference_by_mood',self.voice.config)

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg requis pour le test vidéo')
    def test_video_is_prepared_locally_with_eight_timestamped_images(self):
        import subprocess
        video=self.inbox/'video.mp4'
        subprocess.run(['ffmpeg','-nostdin','-v','error','-y','-f','lavfi','-i','sine=frequency=300:sample_rate=16000:duration=2',
                        '-f','lavfi','-i','testsrc2=size=320x180:rate=5:duration=2','-c:v','mpeg4','-c:a','aac','-shortest',str(video)],
                        capture_output=True,check=True,timeout=30)
        pack(self.inbox,self.root/'video.tar.gz');install(self.root/'video.tar.gz',self.catalog)
        identifier=digest_file(video);media=prepare(self.catalog,identifier)
        self.assertEqual(len(media['frames']),8)
        self.assertTrue(all(0<=frame['time']<media['duration'] for frame in media['frames']))
        self.assertTrue(all((self.catalog.derived(identifier)/frame['file']).is_file() for frame in media['frames']))

    def test_api_requires_key_and_transcript_can_be_corrected(self):
        identifier=self.prepared();worker=Mock();worker.status.return_value={'automatic':False,'message':'Pause','active':False}
        app=FastAPI();app.include_router(build_media_router())
        app.dependency_overrides[get_hardware]=lambda:self.hardware
        app.dependency_overrides[get_media]=lambda:self.catalog
        app.dependency_overrides[get_media_worker]=lambda:worker
        headers={'X-Bender-Control-Token':self.hardware.control_token()}
        with TestClient(app) as client:
            self.assertEqual(client.get('/api/media').status_code,403)
            self.assertEqual(client.post('/api/media/resume').status_code,403)
            self.assertEqual(client.get(f'/api/media/{identifier}/audio').status_code,403)
            self.assertEqual(client.get('/api/media',headers=headers).status_code,200)
            response=client.post(f'/api/media/{identifier}/retry',headers=headers,json={'transcript':'texte corrigé'})
            self.assertEqual(response.status_code,200)
            self.assertEqual(self.catalog.get(identifier)['media']['transcript'],'texte corrigé')
            self.assertEqual(client.get(f'/api/media/{identifier}/audio',headers=headers).status_code,200)
            client.post(f'/api/media/{identifier}/retry',headers=headers,json={'transcript':''})
            self.assertFalse(self.catalog.get(identifier)['media']['transcribed'])
        self.assertEqual(worker.start.call_count,2)
