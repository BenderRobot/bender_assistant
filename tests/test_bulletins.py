from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from bender_voice.bulletins import Bulletins, chunks, parse_feed
from bender_voice.service import VoiceService
from bender_voice.config import load_config
from bender_voice.providers import VoiceUnavailable
from bulletin_api import router
from hardware_api import require_control
from voice_api import get_voice
from test_voice import FakeVoice


class BulletinTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        self.config={'data_dir':str(self.root),'local_provider':'chatterbox','system_fallback':True,
                     'elevenlabs':{'enabled':True,'daily_character_limit':10000},'lipsync':{'engine':'acoustic'}}
        self.providers={name:FakeVoice(name) for name in ('chatterbox','elevenlabs','system')}
        self.voice=VoiceService(self.config,self.providers)
        # 06:00 in Paris, while the server clock is UTC.
        self.now=datetime(2026,10,24,4,0,tzinfo=timezone.utc)
        self.bulletins=Bulletins(self.voice,lambda:self.now)
        self.bulletins.configure(dict(enabled=True,feeds=['https://example.org/rss'],mood='excited'))

    def items(self,*args):
        return [dict(title='Un titre de test',summary='Un court résumé de la rédaction.',source='Source de test',
                     url='https://example.org/article',published=self.now.isoformat())]

    def test_conversation_uses_cloud_and_never_waits_for_chatterbox_on_failure(self):
        result=self.voice.prepare('Bonjour en direct')
        self.assertEqual(result['segments'][0]['source'],'elevenlabs')
        self.providers['elevenlabs'].fail=True
        failed=self.voice.prepare('Une autre réponse')
        self.assertEqual(failed['segments'][0]['source'],'system')
        self.assertEqual(self.providers['chatterbox'].calls,0)

    def test_disabled_cloud_does_not_run_slow_local_in_auto(self):
        self.config['elevenlabs']['enabled']=False
        result=self.voice.prepare('Pas de clé configurée')
        self.assertEqual(result['segments'][0]['source'],'system')
        self.assertEqual(self.providers['chatterbox'].calls,0)
        self.assertEqual(self.providers['elevenlabs'].calls,0)

    def test_due_time_date_and_playback_do_not_trigger_regeneration(self):
        self.now-=timedelta(minutes=1)
        fetch=Mock(side_effect=self.items)
        self.assertEqual(self.bulletins.run_due(fetch)['state'],'absent');fetch.assert_not_called()
        self.now+=timedelta(minutes=1)
        job=self.bulletins.run_due(fetch)
        self.assertEqual(job['state'],'ready');self.assertGreater(job['done'],0)
        calls=self.providers['chatterbox'].calls
        self.assertEqual(self.providers['elevenlabs'].calls,0)
        self.assertTrue(all(s['cached'] for s in self.bulletins.playback()['segments']))
        self.bulletins.run_due(fetch)
        self.assertEqual(self.providers['chatterbox'].calls,calls);self.assertEqual(fetch.call_count,1)
        self.assertTrue(self.bulletins.answer('Lis-moi les infos')['prepared_bulletin'])
        self.assertIsNone(self.bulletins.answer('Allume la lumière'))
        self.now+=timedelta(days=1)
        with self.assertRaisesRegex(ValueError,'pas encore prêt'):self.bulletins.playback()

    def test_catch_up_and_manual_queue_when_schedule_is_disabled(self):
        self.now+=timedelta(hours=3)
        self.assertEqual(self.bulletins.run_due(self.items)['state'],'ready')
        self.now+=timedelta(days=1)
        self.bulletins.configure(dict(enabled=False,feeds=['https://example.org/rss']))
        self.assertEqual(self.bulletins.run_due(self.items)['state'],'absent')
        self.bulletins.queue()
        self.assertEqual(self.bulletins.run_due(self.items)['state'],'ready')

    def test_failure_is_not_published_or_retried_automatically_and_never_calls_cloud(self):
        self.providers['chatterbox'].fail=True
        self.assertEqual(self.bulletins.run_due(self.items)['state'],'error')
        self.assertEqual(self.providers['elevenlabs'].calls,0)
        calls=self.providers['chatterbox'].calls
        self.bulletins.run_due(self.items)
        self.assertEqual(self.providers['chatterbox'].calls,calls)
        with self.assertRaises(ValueError):self.bulletins.playback()
        self.providers['chatterbox'].fail=False;self.bulletins.queue()
        self.assertEqual(self.bulletins.run_due(self.items)['state'],'ready')

    def test_rss_and_atom_filter_old_items_and_keep_attribution(self):
        rss=b'''<rss><channel><title>Journal</title><item><title>Actuel</title><description>&lt;p&gt;Texte propre&lt;/p&gt;</description><pubDate>Sat, 24 Oct 2026 03:00:00 GMT</pubDate><link>https://example.org/a</link></item><item><title>Ancien</title><pubDate>Wed, 21 Oct 2026 03:00:00 GMT</pubDate></item></channel></rss>'''
        entries=parse_feed(rss,'https://example.org/rss',self.now)
        self.assertEqual(len(entries),1);self.assertEqual(entries[0]['summary'],'Texte propre')
        self.assertEqual(entries[0]['source'],'Journal')
        atom=b'''<feed xmlns="http://www.w3.org/2005/Atom"><title>Autre journal</title><entry><title>Un titre</title><updated>2026-10-24T03:00:00Z</updated><link href="https://example.org/b"/></entry></feed>'''
        self.assertEqual(parse_feed(atom,'https://example.org/atom',self.now)[0]['url'],'https://example.org/b')
        for xml in ('<!DOCTYPE rss [<!ENTITY x "text">]><rss/>'.encode(), '<!DOCTYPE rss><rss/>'.encode('utf-16')):
            with self.assertRaises(ValueError):parse_feed(xml,'https://example.org/rss',self.now)
        parts=chunks(' '.join(['Texte.']*150))
        self.assertTrue(all(len(part)<=230 for part in parts))
        self.assertEqual(' '.join(parts),' '.join(['Texte.']*150))

    def test_missing_source_does_not_publish_old_or_empty_audio(self):
        self.assertEqual(self.bulletins.run_due(lambda *args:[])['state'],'error')
        self.assertEqual(self.providers['chatterbox'].calls,0)
        self.assertEqual(self.providers['elevenlabs'].calls,0)

    def test_protected_settings_queue_and_playback(self):
        app=FastAPI();app.include_router(router)
        app.dependency_overrides[get_voice]=lambda:self.voice
        with TestClient(app) as client:
            self.assertEqual(client.get('/api/bulletins').status_code,403)
            self.assertEqual(client.post('/api/voice/live-settings',json={}).status_code,403)
            app.dependency_overrides[require_control]=lambda:None
            self.assertEqual(client.post('/api/bulletins/settings',json={'enabled':True,'feeds':['file:///etc/passwd']}).status_code,400)
            self.assertEqual(client.post('/api/bulletins/settings',json={'time':'35:88'}).status_code,422)
            self.assertEqual(client.post('/api/bulletins/play').status_code,409)
            value={'enabled':True,'voice_id':'test-voice','model_id':'eleven_flash_v2_5'}
            self.assertEqual(client.post('/api/voice/live-settings',json=value).status_code,200)
            config_path=self.root/'voice.json';config_path.write_text(json.dumps(self.config),encoding='utf-8')
            self.assertEqual(load_config(config_path)['elevenlabs']['voice_id'],'test-voice')
            self.assertNotIn('api_key',(self.root/'live-settings.json').read_text())

    def test_dst_uses_paris_time_and_no_duplicate_for_same_day(self):
        self.now=datetime(2026,10,25,4,59,tzinfo=timezone.utc)
        self.assertEqual(self.bulletins.run_due(self.items)['state'],'absent')
        self.now+=timedelta(minutes=1)
        self.assertEqual(self.bulletins.run_due(self.items)['state'],'ready')
        calls=self.providers['chatterbox'].calls
        self.now+=timedelta(hours=2)
        self.bulletins.run_due(self.items)
        self.assertEqual(self.providers['chatterbox'].calls,calls)

    def test_two_workers_do_not_generate_the_bulletin_twice(self):
        other=Bulletins(self.voice,lambda:self.now)
        fetch=Mock(side_effect=self.items)
        with ThreadPoolExecutor(2) as pool:
            list(pool.map(lambda service:service.run_due(fetch),[self.bulletins,other]))
        self.assertEqual(self.bulletins.today()['state'],'ready')
        self.assertEqual(fetch.call_count,1)

    def test_processing_worker_in_this_process_is_checked_without_a_signal(self):
        entered=threading.Event();release=threading.Event()
        def fetch(*args):
            entered.set()
            if not release.wait(5):raise TimeoutError('test worker not released')
            return self.items(*args)
        other=Bulletins(self.voice,lambda:self.now)
        with ThreadPoolExecutor(1) as pool:
            running=pool.submit(self.bulletins.run_due,fetch)
            try:
                self.assertTrue(entered.wait(5))
                with patch('bender_voice.processes.os.kill',side_effect=AssertionError('signal forbidden')):
                    self.assertEqual(other.run_due(self.items)['state'],'processing')
            finally:release.set()
            self.assertEqual(running.result(timeout=5)['state'],'ready')

    def test_chat_reads_prepared_audio_without_the_brain_or_new_cloud_speech(self):
        import memory
        with patch.object(memory,'DB_PATH',str(self.root/'chat-memory.db')):
            import server
        self.bulletins.run_due(self.items)
        before={name:provider.calls for name,provider in self.providers.items()}
        previous=dict(server.app.dependency_overrides)
        try:
            server.app.dependency_overrides[require_control]=lambda:None
            with TestClient(server.app) as client,patch('server.get_voice',return_value=self.voice),patch('server.process_command') as brain,patch('bender_voice.bulletins.Bulletins',return_value=self.bulletins):
                result=client.post('/api/chat',json={'message':'Lis-moi les infos'}).json()
                self.assertTrue(result['prepared_bulletin'])
                self.assertEqual(result['speech']['segments'][0]['source'],'chatterbox')
                brain.assert_not_called()
            self.assertEqual(before,{name:provider.calls for name,provider in self.providers.items()})
        finally:server.app.dependency_overrides.clear();server.app.dependency_overrides.update(previous)
