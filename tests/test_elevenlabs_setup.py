import json
from pathlib import Path
import runpy
import tempfile
import unittest

from bender_voice.config import load_config
from bender_voice.live_settings import save

ROOT = Path(__file__).resolve().parents[1]
install = runpy.run_path(str(ROOT / 'scripts' / 'install-elevenlabs-settings.py'))['install']


class ElevenLabsSetupTests(unittest.TestCase):
    def test_deployment_settings_reach_the_configured_data_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / 'voice.json'
            config.write_text(json.dumps({'data_dir': 'custom-voice-data', 'local_provider': 'system'}))
            source = root / 'settings.json'
            settings = {'enabled': True, 'voice_id': 'test-voice', 'model_id': 'eleven_flash_v2_5'}
            source.write_text(json.dumps(settings))
            install(source, config)
            self.assertEqual(load_config(config)['elevenlabs'], settings)
            self.assertEqual(json.loads(config.read_text())['data_dir'], 'custom-voice-data')

    def test_invalid_settings_do_not_replace_the_current_voice(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / 'voice.json'
            config.write_text(json.dumps({'data_dir': 'voice-data', 'local_provider': 'system'}))
            source = root / 'settings.json'
            settings = {'enabled': True, 'voice_id': 'valid-test-voice', 'model_id': 'eleven_flash_v2_5'}
            source.write_text(json.dumps(settings))
            install(source, config)
            for invalid in ({**settings, 'voice_id': ''}, {**settings, 'voice_id': '../outside'},
                            {**settings, 'model_id': 'unknown-model'}):
                source.write_text(json.dumps(invalid))
                with self.assertRaises(ValueError):
                    install(source, config)
                self.assertEqual(load_config(config)['elevenlabs'], settings)

    def test_unchanged_windows_settings_preserve_later_debian_workshop_edits(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / 'voice.json'
            config.write_text(json.dumps({'data_dir': 'voice-data', 'local_provider': 'system'}))
            source = root / 'settings.json'
            settings = {'enabled': True, 'voice_id': 'first-voice', 'model_id': 'eleven_flash_v2_5'}
            source.write_text(json.dumps(settings))
            self.assertTrue(install(source, config))
            remote_choice = {**settings, 'voice_id': 'chosen-on-debian'}
            save(root / 'voice-data', remote_choice)
            self.assertFalse(install(source, config))
            self.assertEqual(load_config(config)['elevenlabs'], remote_choice)
            settings['voice_id'] = 'new-windows-choice'
            source.write_text(json.dumps(settings))
            self.assertTrue(install(source, config))
            self.assertEqual(load_config(config)['elevenlabs'], settings)
