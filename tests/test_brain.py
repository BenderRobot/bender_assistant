import base64
import json
from pathlib import Path
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient
import jwt
import requests

from bender_brain import BrainError
from bender_brain.auth import Auth, DIRECT_SCOPE, ISSUER, RESOURCE, account_id
from bender_brain.client import Client, response_text
from brain_api import build_brain_router, get_brain
from hardware_api import require_control


class Reply:
    def __init__(self, data=None, status=200, events=None, lines=None):
        self.data, self.status_code = data, status
        self.lines = lines if lines is not None else [line for event in (events or []) for line in ('data: ' + json.dumps(event), '')]
        self.closed = False

    def json(self): return self.data
    def iter_lines(self): return iter(self.lines)
    def close(self): self.closed = True
    def __enter__(self): return self
    def __exit__(self, *args): self.close()


class BrainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.http = Mock()
        self.auth = Auth(self.temp.name, self.http)
        self.auth.jwks = Mock()
        self.auth.jwks.get_signing_key_from_jwt.return_value = Mock(key=self.key.public_key())

    def tearDown(self): self.temp.cleanup()

    def tokens(self, attempt, client='issued-bender', scopes=DIRECT_SCOPE, subject='person-1', **overrides):
        claims = dict(iss=ISSUER, aud=client, sub=subject, iat=int(time.time()), exp=int(time.time())+3600,
                      nonce=attempt.nonce, email='robot@example.test')
        claims.update(overrides)
        return dict(access_token='private-access', refresh_token='private-refresh', token_type='Bearer',
                    id_token=jwt.encode(claims, self.key, algorithm='RS256'), expires_in=3600, scope=scopes)

    def connected(self, client='issued-bender', subject='person-1', new=False):
        attempt = self.auth.begin(new=new)
        self.http.post.return_value = Reply(self.tokens(attempt, client=client, subject=subject))
        self.auth.complete(attempt, dict(state=attempt.state, code='private-code', client_id=client))
        return account_id(client)

    def test_pkce_host_id_and_issued_client_id_are_used(self):
        attempt = self.auth.begin()
        params = parse_qs(urlsplit(attempt.url()).query)
        self.assertEqual(params['client_id'], ['dynamic_agent_client'])
        self.assertEqual(params['resource'], [RESOURCE])
        self.assertEqual(params['redirect_uri'], ['http://127.0.0.1:1455/auth/callback'])
        self.assertEqual(params['code_challenge_method'], ['S256'])
        self.assertNotIn(attempt.verifier, attempt.url())
        self.assertEqual(self.auth.begin().host_id, attempt.host_id)
        self.http.post.return_value = Reply(self.tokens(attempt))
        self.auth.complete(attempt, dict(state=attempt.state, code='private-code', client_id='issued-bender'))
        data = self.http.post.call_args.kwargs['data']
        self.assertEqual(data['client_id'], 'issued-bender')
        self.assertEqual(data['code_verifier'], attempt.verifier)
        returning = self.auth.begin()
        self.assertEqual(returning.client_id, 'issued-bender')
        self.assertNotIn('agent_name_hint', parse_qs(urlsplit(returning.url()).query))
        self.assertNotEqual(returning.state, attempt.state)

    def test_state_rejects_before_token_exchange_and_does_not_consume(self):
        attempt = self.auth.begin()
        with self.assertRaises(BrainError):
            self.auth.complete(attempt, dict(state='wrong', code='private-code', client_id='issued'))
        self.http.post.assert_not_called()
        self.assertFalse(attempt.consumed)

    def test_consent_denial_and_expired_attempt(self):
        attempt = self.auth.begin()
        with self.assertRaises(BrainError): self.auth.complete(attempt, dict(state=attempt.state, error='access_denied'))
        self.http.post.assert_not_called()
        attempt = self.auth.begin(); attempt.created_at -= 601
        with self.assertRaises(BrainError): self.auth.complete(attempt, dict(state=attempt.state, code='code', client_id='issued'))

    def test_signature_audience_nonce_issuer_expiry_and_subject_validation(self):
        for changes in [dict(aud='another-client'), dict(iss='https://attacker.test'), dict(nonce='other'), dict(exp=1), dict(sub='')]:
            with self.subTest(changes=changes):
                attempt = self.auth.begin()
                self.http.post.return_value = Reply(self.tokens(attempt, **changes))
                with self.assertRaises(BrainError):
                    self.auth.complete(attempt, dict(state=attempt.state, code='code', client_id='issued-bender'))
                self.assertFalse(self.auth.status()['connected'])
        attempt = self.auth.begin()
        data = self.tokens(attempt); data['id_token'] = jwt.encode(dict(iss=ISSUER), 'wrong-key' * 8, algorithm='HS256')
        self.http.post.return_value = Reply(data)
        with self.assertRaises(BrainError): self.auth.complete(attempt, dict(state=attempt.state, code='code', client_id='issued-bender'))

    def test_scope_missing_blocks_all_inference(self):
        attempt = self.auth.begin()
        self.http.post.return_value = Reply(self.tokens(attempt, scopes='openid profile'))
        status = self.auth.complete(attempt, dict(state=attempt.state, code='code', client_id='issued-bender'))
        self.assertFalse(status['authorized'])
        with self.assertRaises(BrainError): self.auth.credential()

    def test_returning_identity_mismatch_keeps_previous_account(self):
        self.connected()
        before = self.auth.path.read_bytes()
        attempt = self.auth.begin()
        self.http.post.return_value = Reply(self.tokens(attempt, subject='person-2'))
        with self.assertRaises(BrainError): self.auth.complete(attempt, dict(state=attempt.state, code='code'))
        self.assertEqual(before, self.auth.path.read_bytes())

    def test_refresh_rotation_and_scope_preservation(self):
        identifier = self.connected()
        with self.auth.locked():
            doc = self.auth._read(); doc['accounts'][identifier]['expires_at'] = 1; self.auth._write(doc)
        self.http.post.return_value = Reply(dict(access_token='new-private-access', refresh_token='new-private-refresh', token_type='Bearer', expires_in=1000))
        selected, record = self.auth.credential()
        self.assertEqual(record['refresh_token'], 'new-private-refresh')
        self.assertIn(DIRECT_SCOPE, record['scopes'])
        form = self.http.post.call_args.kwargs['data']
        self.assertEqual(form['grant_type'], 'refresh_token')
        self.assertNotIn('scope', form)
        self.auth.credential()
        self.assertEqual(self.http.post.call_count, 2)  # One exchange, one refresh.

    def test_parallel_refreshes_only_exchange_once(self):
        identifier = self.connected()
        with self.auth.locked():
            doc = self.auth._read(); doc['accounts'][identifier]['expires_at'] = 1; self.auth._write(doc)
        self.http.post.return_value = Reply(dict(access_token='new-private-access', refresh_token='rotated-refresh', token_type='Bearer', expires_in=1000))
        other = Auth(self.temp.name, self.http)
        with ThreadPoolExecutor(max_workers=2) as pool:
            records = list(pool.map(lambda auth: auth.credential()[1], [self.auth, other]))
        self.assertEqual([item['refresh_token'] for item in records], ['rotated-refresh'] * 2)
        self.assertEqual(self.http.post.call_count, 2)

    def test_temporary_refresh_failure_keeps_credentials_but_rejection_clears_them(self):
        identifier = self.connected()
        with self.auth.locked():
            doc = self.auth._read(); doc['accounts'][identifier]['expires_at'] = 1; self.auth._write(doc)
        before = self.auth.path.read_bytes()
        self.http.post.side_effect = requests.ConnectionError('not-public')
        with self.assertRaises(BrainError): self.auth.credential()
        self.assertEqual(before, self.auth.path.read_bytes())
        self.http.post.side_effect = None; self.http.post.return_value = Reply(status=400)
        with self.assertRaises(BrainError): self.auth.credential()
        self.assertFalse(self.auth.status()['connected'])

    def test_public_status_never_exposes_tokens_or_email(self):
        self.connected()
        public = json.dumps(self.auth.status())
        for word in ('private-', 'robot@example', 'id_token', 'subject', 'client_id'):
            self.assertNotIn(word, public)
        self.assertEqual(len(self.auth.status(private=True)['accounts']), 1)

    def test_logout_revokes_and_retains_registration(self):
        identifier = self.connected()
        self.http.post.return_value = Reply(status=200)
        self.assertTrue(self.auth.logout())
        self.assertFalse(self.auth.status()['connected'])
        self.assertEqual(self.auth.begin().client_id, 'issued-bender')
        self.assertNotIn('access_token', self.auth._read()['accounts'][identifier])
        self.assertEqual(self.http.post.call_args.kwargs['data']['token_type_hint'], 'refresh_token')

    def test_logout_network_failure_clears_local_credentials(self):
        self.connected(); self.http.post.side_effect = requests.ConnectionError('not-public')
        self.assertFalse(self.auth.logout())
        self.assertFalse(self.auth.status()['connected'])

    def test_models_filter_preserves_order_and_validates_choice(self):
        self.connected()
        http = Mock()
        http.request.return_value = Reply(dict(models=[dict(slug='hidden', visibility='hide'),
                         dict(slug='first', display_name='Premier', visibility='list'), dict(slug='second', visibility='list')]))
        brain = Client(self.auth, http)
        self.assertEqual([item['slug'] for item in brain.models()['models']], ['first', 'second'])
        with self.assertRaises(BrainError): brain.choose_model('hidden')
        brain.choose_model('second')
        self.assertEqual(self.auth.status()['model'], 'second')

    def test_completed_stream_and_partial_failure(self):
        delta = dict(type='response.output_text.delta', delta='Salut.')
        self.assertEqual(response_text(Reply(events=[delta, dict(type='response.completed', response=dict(status='completed'))])), 'Salut.')
        for terminal in [None, dict(type='response.failed', response=dict(error=dict(code='subscription_sharing_usage_limit_exceeded'))), dict(type='response.incomplete')]:
            with self.subTest(terminal=terminal):
                with self.assertRaises(BrainError): response_text(Reply(events=[delta]+([terminal] if terminal else [])))

    def test_request_contract_and_account_isolated_history(self):
        first = self.connected(); self.auth.select_model(first, 'available-model')
        http = Mock()
        http.request.side_effect = lambda *args, **kwargs: Reply(events=[dict(type='response.output_text.delta', delta='Réponse de Bender.'),dict(type='response.completed')])
        brain = Client(self.auth, http)
        self.assertEqual(brain.respond('Bonjour', image_bytes=b'jpeg'), 'Réponse de Bender.')
        kwargs = http.request.call_args.kwargs
        payload = kwargs['json']
        self.assertFalse(payload['store']); self.assertTrue(payload['stream']); self.assertFalse(kwargs['allow_redirects'])
        self.assertEqual(set(payload), {'model','input','instructions','store','stream'})
        self.assertTrue(payload['input'][-1]['content'][1]['image_url'].startswith('data:image/jpeg;base64,'))
        brain.respond('La suite')
        self.assertEqual(len(http.request.call_args.kwargs['json']['input']), 3)
        second = self.connected(client='issued-other', subject='person-2', new=True)
        self.auth.select_model(second, 'available-model')
        brain.respond('Autre compte')
        self.assertEqual(len(http.request.call_args.kwargs['json']['input']), 1)
        self.assertEqual(len(self.auth.status(private=True)['accounts']), 2)

    def test_failed_stream_saves_no_partial_exchange(self):
        identifier = self.connected(); self.auth.select_model(identifier, 'available-model')
        http = Mock(); http.request.return_value = Reply(events=[dict(type='response.output_text.delta',delta='Ne pas mémoriser')])
        brain = Client(self.auth,http)
        with self.assertRaises(BrainError): brain.respond('Question')
        with brain._history_db() as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM exchanges').fetchone()[0], 0)

    def test_conversation_uses_low_effort_for_the_documented_sol_model(self):
        identifier=self.connected();self.auth.select_model(identifier,'gpt-6.1-sol')
        http=Mock()
        http.request.side_effect=lambda *args,**kwargs:Reply(events=[dict(type='response.output_text.delta',delta='Salut.'),dict(type='response.completed')])
        client=Client(self.auth,http)
        client.respond('Pourquoi le ciel est bleu ?')
        payload=http.request.call_args.kwargs['json']
        self.assertEqual(payload['reasoning'],{'effort':'low'})
        self.assertIn('une ou deux phrases',payload['instructions'])
        self.assertNotIn('service_tier',payload)
        client.respond('Analyse cette photo',image_bytes=b'jpeg')
        self.assertNotIn('reasoning',http.request.call_args.kwargs['json'])
        self.assertNotIn('une ou deux phrases',http.request.call_args.kwargs['json']['instructions'])

    def test_network_errors_are_safe_to_display(self):
        identifier = self.connected(); self.auth.select_model(identifier, 'available-model')
        http = Mock(); http.request.side_effect = requests.ConnectionError('private-access')
        with self.assertRaises(BrainError) as caught: Client(self.auth,http).respond('Pourquoi le ciel est bleu ?')
        self.assertNotIn('private-access', str(caught.exception))

    def test_exact_greeting_has_no_remote_request_and_stays_in_account_history(self):
        identifier=self.connected();http=Mock();client=Client(self.auth,http)
        answer=client.respond('Salut, Bender !')
        self.assertIn('Salut Benjamin',answer)
        self.assertEqual(answer.timing_metadata,{'brain_source':'local'})
        http.request.assert_not_called()
        with client._history_db() as conn:
            rows=conn.execute('SELECT account,user,answer FROM exchanges').fetchall()
        self.assertEqual(rows,[(identifier,'Salut, Bender !',str(answer))])
        self.auth.logout()
        with self.assertRaises(BrainError):client.respond('salut')

    def test_repeated_greeting_reuses_elevenlabs_audio_without_gpt_or_new_synthesis(self):
        from bender_voice.service import VoiceService
        from test_voice import FakeVoice
        self.connected();http=Mock();client=Client(self.auth,http)
        providers={name:FakeVoice(name) for name in ('elevenlabs','chatterbox','system')}
        voice=VoiceService({'data_dir':str(Path(self.temp.name)/'voice'),
                            'lipsync':{'engine':'acoustic'},'elevenlabs':{'enabled':True}},providers)
        first=voice.prepare(client.respond('salut'),mode='cloud')
        second=voice.prepare(client.respond('Salut !'),mode='cloud')
        http.request.assert_not_called()
        self.assertEqual(providers['elevenlabs'].calls,1)
        self.assertEqual(providers['chatterbox'].calls,0)
        self.assertEqual(first['segments'][0]['id'],second['segments'][0]['id'])
        self.assertTrue(second['segments'][0]['cached'])

    def test_quick_phrases_do_not_swallow_questions_or_contextual_acknowledgements(self):
        from bender_brain.quick_replies import quick_reply
        for text in ('salut','BONJOUR !','merci Bender','à bientôt'):
            self.assertIsNotNone(quick_reply(text))
        for text in ('salut explique-moi la météo','ne dis pas salut','merci mais comment ça marche ?',
                     'oui','non','ok','ça va ?','salut demain à 6 heures'):
            self.assertIsNone(quick_reply(text),text)

    def test_conversation_prefers_available_luna_without_changing_vision_or_saved_model(self):
        identifier=self.connected();self.auth.select_model(identifier,'gpt-6.1-sol')
        http=Mock();client=Client(self.auth,http)
        def request(method,path,**kwargs):
            if method=='GET':
                return Reply(dict(models=[dict(slug='gpt-6-luna',visibility='list')]))
            return Reply(events=[dict(type='response.output_text.delta',delta='Une réponse.'),dict(type='response.completed')])
        http.request.side_effect=request
        first=client.respond('Quelle est la couleur du ciel ?')
        self.assertEqual(first.timing_metadata['brain_model'],'gpt-6-luna')
        self.assertEqual(first.timing_metadata['brain_effort'],'none')
        self.assertEqual(http.request.call_args.kwargs['json']['reasoning'],{'effort':'none'})
        client.respond('Et la mer ?')
        self.assertEqual(sum(call.args[0]=='GET' for call in http.request.call_args_list),1)
        client.respond('Décris cette photo',image_bytes=b'jpeg')
        self.assertEqual(http.request.call_args.kwargs['json']['model'],'gpt-6.1-sol')
        self.assertNotIn('reasoning',http.request.call_args.kwargs['json'])
        self.assertEqual(self.auth.status()['model'],'gpt-6.1-sol')

    def test_unavailable_light_model_keeps_selected_model_and_caches_the_lookup(self):
        identifier=self.connected();self.auth.select_model(identifier,'gpt-6.1-sol')
        http=Mock();client=Client(self.auth,http)
        def request(method,path,**kwargs):
            if method=='GET':return Reply(dict(models=[dict(slug='gpt-6.1-sol',visibility='list')]))
            return Reply(events=[dict(type='response.output_text.delta',delta='Une réponse.'),dict(type='response.completed')])
        http.request.side_effect=request
        self.assertEqual(client.respond('Une question').timing_metadata['brain_model'],'gpt-6.1-sol')
        client.respond('Une autre question')
        self.assertEqual(sum(call.args[0]=='GET' for call in http.request.call_args_list),1)
        self.assertEqual(http.request.call_args.kwargs['json']['reasoning'],{'effort':'low'})

    def test_web_settings_require_control_and_public_status_is_safe(self):
        self.connected()
        app = FastAPI(); app.include_router(build_brain_router())
        app.dependency_overrides[get_brain] = lambda: Client(self.auth)
        with TestClient(app) as client:
            self.assertEqual(client.get('/api/brain/status').status_code, 200)
            self.assertEqual(client.get('/api/brain/accounts').status_code, 403)
            self.assertEqual(client.get('/api/brain/models').status_code, 403)
            self.assertEqual(client.post('/api/brain/logout').status_code, 403)
            app.dependency_overrides[require_control] = lambda: None
            self.assertEqual(client.get('/api/brain/accounts').json()['active_account'], account_id('issued-bender'))

    def test_chat_to_voice_pipeline_and_control_requirement(self):
        import memory
        # Import the real server without touching the user's conversation database.
        with patch.object(memory, 'DB_PATH', str(Path(self.temp.name) / 'old-memory.db')):
            import server
        from voice_api import get_voice
        voice = Mock(); voice.prepare.return_value = dict(segments=[dict(id='speech-test')])
        previous = dict(server.app.dependency_overrides)
        try:
            server.app.dependency_overrides[get_voice] = lambda: voice
            with TestClient(server.app) as client, patch('server.get_voice', return_value=voice), patch('server.process_command', return_value='Salut l’organique.') as respond:
                self.assertEqual(client.post('/api/chat', json=dict(message='Bonjour')).status_code, 403)
                respond.assert_not_called()
                server.app.dependency_overrides[require_control] = lambda: None
                data = client.post('/api/chat', json=dict(message='Bonjour', mode='local')).json()
                self.assertEqual(data['response'], 'Salut l’organique.')
                self.assertEqual(data['speech']['segments'][0]['id'], 'speech-test')
                self.assertGreaterEqual(data['timings']['brain_seconds'],0)
                self.assertGreaterEqual(data['timings']['voice_seconds'],0)
                voice.prepare.assert_called_once_with('Salut l’organique.', 'local', 'neutral', 'Bonjour', '', False)
                voice.reset_mock()
                result = client.post('/api/chat', json=dict(message='Texte uniquement', speech=False)).json()
                self.assertIn('response', result); self.assertNotIn('speech', result)
                self.assertNotIn('voice_seconds',result['timings'])
                voice.prepare.assert_not_called()
        finally:
            server.app.dependency_overrides.clear(); server.app.dependency_overrides.update(previous)

    def test_chat_error_is_actionable_and_never_synthesized(self):
        import memory
        with patch.object(memory, 'DB_PATH', str(Path(self.temp.name) / 'old-memory.db')):
            import server
        from voice_api import get_voice
        voice = Mock()
        previous = dict(server.app.dependency_overrides)
        try:
            server.app.dependency_overrides[require_control] = lambda: None
            server.app.dependency_overrides[get_voice] = lambda: voice
            with TestClient(server.app) as client, patch('server.get_voice', return_value=voice), patch('server.process_command', side_effect=BrainError('Compte à reconnecter.')):
                result = client.post('/api/chat', json=dict(message='Bonjour')).json()
                self.assertEqual(result['error'], 'Compte à reconnecter.')
                voice.prepare.assert_not_called()
        finally:
            server.app.dependency_overrides.clear(); server.app.dependency_overrides.update(previous)

    def test_chat_reports_local_answer_without_claiming_a_gpt_call(self):
        import memory
        with patch.object(memory,'DB_PATH',str(Path(self.temp.name)/'old-memory.db')):
            import server
        from bender_brain.client import BrainAnswer
        previous=dict(server.app.dependency_overrides)
        try:
            server.app.dependency_overrides[require_control]=lambda:None
            with TestClient(server.app) as client,patch('server.process_command',return_value=BrainAnswer('Salut.',source='local')):
                result=client.post('/api/chat',json={'message':'salut','speech':False}).json()
            self.assertEqual(result['response'],'Salut.')
            self.assertEqual(result['timings']['brain_source'],'local')
            self.assertNotIn('brain_model',result['timings'])
        finally:
            server.app.dependency_overrides.clear();server.app.dependency_overrides.update(previous)
