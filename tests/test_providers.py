import base64
import io
import json
import os
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from bender_voice.providers import ChatterboxVoice, ElevenVoice, VoiceUnavailable


class ProviderTests(unittest.TestCase):
    def test_eleven_payload_and_character_alignment(self):
        with tempfile.TemporaryDirectory() as temp:
            config = {'elevenlabs': {'enabled': True, 'voice_id': 'test-voice', 'model_id': 'eleven_multilingual_v2'}}
            provider = ElevenVoice(config)
            payload = {'audio_base64': base64.b64encode(b'test-mp3').decode(), 'normalized_alignment': {'characters': ['a']}}
            response = io.BytesIO(json.dumps(payload).encode())
            def convert(source, target):
                self.assertEqual(source.read_bytes(), b'test-mp3')
                target.write_bytes(b'converted-wav')
            with patch.dict(os.environ, {'ELEVENLABS_API_KEY': 'test-key'}), patch('urllib.request.urlopen', return_value=response) as request, patch('bender_voice.providers.convert_audio', side_effect=convert):
                target = Path(temp) / 'voice.wav'
                alignment = provider.synthesize('Bonjour', 'neutral', target)
                sent = request.call_args.args[0]
                self.assertTrue(sent.full_url.startswith('https://api.elevenlabs.io/v1/text-to-speech/'))
                self.assertEqual(json.loads(sent.data)['text'], 'Bonjour')
                self.assertEqual(alignment, payload['normalized_alignment'])
                self.assertFalse(target.with_suffix('.mp3').exists())

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
