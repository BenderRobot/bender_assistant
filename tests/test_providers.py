import base64
import json
import os
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from bender_voice.providers import ChatterboxVoice, ElevenVoice, VoiceUnavailable


class ProviderTests(unittest.TestCase):
    def test_eleven_payload_and_character_alignment(self):
        with tempfile.TemporaryDirectory() as temp:
            config = {'elevenlabs': {'enabled': True, 'voice_id': 'test-voice', 'model_id': 'eleven_multilingual_v2'}}
            provider = ElevenVoice(config)
            alignment = {'characters': ['a'], 'character_start_times_seconds': [0.0],
                         'character_end_times_seconds': [0.1]}
            payload = {'audio_base64': base64.b64encode(b'test-mp3').decode(), 'normalized_alignment': alignment}
            requests = []
            def handle(request):
                requests.append(request)
                return httpx.Response(200, json=payload)
            transport = httpx.Client(transport=httpx.MockTransport(handle))
            def convert(source, target):
                self.assertEqual(source.read_bytes(), b'test-mp3')
                target.write_bytes(b'converted-wav')
            with patch.dict(os.environ, {'ELEVENLABS_API_KEY': 'test-key'}), patch('httpx.Client', return_value=transport), patch('bender_voice.providers.convert_audio', side_effect=convert):
                target = Path(temp) / 'voice.wav'
                alignment = provider.synthesize('Bonjour', 'neutral', target)
                self.assertEqual(len(requests), 1)
                sent = requests[0]
                self.assertEqual(sent.url.host, 'api.elevenlabs.io')
                self.assertEqual(sent.url.path, '/v1/text-to-speech/test-voice/with-timestamps')
                self.assertEqual(sent.url.params['output_format'], 'mp3_44100_128')
                self.assertEqual(sent.headers['xi-api-key'], 'test-key')
                body = json.loads(sent.content)
                self.assertEqual(body['text'], 'Bonjour')
                self.assertEqual(body['model_id'], 'eleven_multilingual_v2')
                self.assertEqual(alignment, payload['normalized_alignment'])
                self.assertFalse(target.with_suffix('.mp3').exists())
                self.assertEqual(target.read_bytes(), b'converted-wav')

    def test_eleven_failure_is_never_retried_or_exposed(self):
        for failure in (429, 500, 'timeout'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temp:
                requests = []
                def handle(request):
                    requests.append(request)
                    if failure == 'timeout':
                        raise httpx.ReadTimeout('private-server-details', request=request)
                    return httpx.Response(failure, json={'detail': 'private-server-details'})
                transport = httpx.Client(transport=httpx.MockTransport(handle))
                provider = ElevenVoice({'elevenlabs': {'enabled': True, 'voice_id': 'test-voice'}})
                target = Path(temp) / 'voice.wav'
                with patch.dict(os.environ, {'ELEVENLABS_API_KEY': 'test-key'}), patch('httpx.Client', return_value=transport):
                    with self.assertRaisesRegex(VoiceUnavailable, 'aucun nouvel essai') as error:
                        provider.synthesize('Bonjour', 'neutral', target)
                self.assertEqual(len(requests), 1)
                self.assertNotIn('test-key', str(error.exception))
                self.assertNotIn('private-server-details', str(error.exception))
                self.assertFalse(target.exists())
                self.assertFalse(target.with_suffix('.mp3').exists())

    def test_eleven_keeps_original_alignment_when_normalized_is_absent(self):
        alignment = {'characters': ['a'], 'character_start_times_seconds': [0.0],
                     'character_end_times_seconds': [0.1]}
        with tempfile.TemporaryDirectory() as temp:
            transport = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(
                200, json={'audio_base64': base64.b64encode(b'mp3').decode(), 'alignment': alignment})))
            provider = ElevenVoice({'elevenlabs': {'enabled': True, 'voice_id': 'test-voice'}})
            with patch.dict(os.environ, {'ELEVENLABS_API_KEY': 'test-key'}), patch('httpx.Client', return_value=transport), patch('bender_voice.providers.convert_audio'):
                actual = provider.synthesize('a', 'neutral', Path(temp) / 'voice.wav')
            self.assertEqual(actual, alignment)
            self.assertIsInstance(json.dumps(actual), str)

    def test_eleven_uses_current_environment_after_sdk_import_or_key_rotation(self):
        from elevenlabs import ElevenLabs  # Loaded before either test key is set.
        received = []
        for key in ('first-test-key', 'second-test-key'):
            with tempfile.TemporaryDirectory() as temp:
                def handle(request):
                    received.append(request.headers['xi-api-key'])
                    return httpx.Response(200, json={'audio_base64': base64.b64encode(b'mp3').decode()})
                transport = httpx.Client(transport=httpx.MockTransport(handle))
                provider = ElevenVoice({'elevenlabs': {'enabled': True, 'voice_id': 'test-voice'}})
                with patch.dict(os.environ, {'ELEVENLABS_API_KEY': key}), patch('httpx.Client', return_value=transport), patch('bender_voice.providers.convert_audio'):
                    provider.synthesize('Bonjour', 'neutral', Path(temp) / 'voice.wav')
        self.assertEqual(received, ['first-test-key', 'second-test-key'])

    def test_chatterbox_loads_local_and_passes_french_reference(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve();(root/'models').mkdir();(root/'ref.wav').write_bytes(b'reference')
            calls = []
            class Model:
                sr = 24000
                def generate(self, text, **kwargs):
                    calls.append(kwargs)
                    return 'wave-tensor'
            class Factory:
                @staticmethod
                def from_local(path, device):
                    self.assertEqual(path, root/'models');self.assertEqual(device, 'cpu')
                    return Model()
            modules = {'chatterbox': types.ModuleType('chatterbox'), 'chatterbox.mtl_tts': types.SimpleNamespace(ChatterboxMultilingualTTS=Factory),
                       'torchaudio': types.SimpleNamespace(save=lambda path,wav,rate: Path(path).write_bytes(b'audio'))}
            provider = ChatterboxVoice({'data_dir':temp,'reference_by_mood':{'neutral':'ref.wav'},'chatterbox':{'model_dir':'models','device':'cpu'}})
            with patch.dict('sys.modules', modules):
                provider.synthesize('Bonjour', 'sad', root/'out.wav')
            self.assertEqual(calls[0]['language_id'], 'fr')
            self.assertEqual(calls[0]['audio_prompt_path'], str(root/'ref.wav'))


if __name__ == '__main__':
    unittest.main()
