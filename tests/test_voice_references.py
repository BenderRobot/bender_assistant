import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bender_voice.config import load_config
from bender_voice.service import VoiceService


class VoiceReferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.path=self.root/'voice.json'
        self.path.write_text(json.dumps(dict(data_dir='voice-data',local_provider='system',
                                             reference_by_mood={'neutral':'references/original.wav'},
                                             elevenlabs={'enabled':False})),encoding='utf-8')
        self.config=load_config(self.path);self.voice=VoiceService(self.config)
        for name in ('original.wav','eleven-neutral.wav','eleven-sarcastic.wav'):
            (self.voice.store.root/'references'/name).write_bytes(name.encode())

    def test_activation_survives_restart_preserves_config_and_changes_cache_identity(self):
        original=self.path.read_bytes();provider=self.voice.providers['chatterbox']
        before=self.voice._key('Bonjour',provider,'neutral')
        self.voice.activate_reference('references/eleven-neutral.wav')
        self.assertEqual(provider.reference('neutral'),self.voice.store.root/'references/eleven-neutral.wav')
        self.assertNotEqual(before,self.voice._key('Bonjour',provider,'neutral'))
        self.assertEqual(self.voice.config['local_provider'],'chatterbox')
        self.voice.activate_reference('references/eleven-sarcastic.wav','sarcastic')
        restarted=VoiceService(load_config(self.path))
        self.assertEqual(restarted.providers['chatterbox'].reference('sad'),self.voice.store.root/'references/eleven-neutral.wav')
        self.assertEqual(restarted.providers['chatterbox'].reference('sarcastic'),self.voice.store.root/'references/eleven-sarcastic.wav')
        self.assertEqual(original,self.path.read_bytes())
        self.assertFalse(restarted.config['elevenlabs']['enabled'])

    def test_only_existing_wav_references_and_known_moods_are_accepted(self):
        for path,mood in [('missing.wav','neutral'),('../escape.wav','neutral'),('cache/other.wav','neutral'),('references/eleven-neutral.wav','arbitrary')]:
            with self.assertRaises(ValueError):self.voice.activate_reference(path,mood)
        self.assertFalse((self.voice.store.root/'reference-settings.json').exists())
        self.assertEqual(self.voice.config['local_provider'],'system')

    def test_failed_save_does_not_activate_the_reference(self):
        with patch('bender_voice.references.Path.replace',side_effect=OSError('read-only')):
            with self.assertRaises(OSError):self.voice.activate_reference('references/eleven-neutral.wav')
        self.assertEqual(self.voice.config['local_provider'],'system')
        self.assertEqual(self.voice.config['reference_by_mood']['neutral'],'references/original.wav')
        self.assertFalse(list(self.voice.store.root.glob('reference-settings-*.tmp')))
