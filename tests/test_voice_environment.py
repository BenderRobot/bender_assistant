import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bender_voice.environment import load_environment


class EnvironmentTests(unittest.TestCase):
    def test_private_key_file_preserves_other_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.env').write_text('ELEVENLABS_API_KEY=old-test-key\nBENDER_PORT=8124\n')
            (root / '.env.elevenlabs').write_text('ELEVENLABS_API_KEY=new-test-key\n')
            with patch.dict(os.environ, {}, clear=True):
                load_environment(root)
                self.assertEqual(os.environ['ELEVENLABS_API_KEY'], 'new-test-key')
                self.assertEqual(os.environ['BENDER_PORT'], '8124')

    def test_explicit_process_settings_are_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.env.elevenlabs').write_text('ELEVENLABS_API_KEY=file-test-key\n')
            with patch.dict(os.environ, {'ELEVENLABS_API_KEY': 'process-test-key'}, clear=True):
                load_environment(root)
                self.assertEqual(os.environ['ELEVENLABS_API_KEY'], 'process-test-key')

    def test_existing_env_still_works_without_a_separate_elevenlabs_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.env').write_text('ELEVENLABS_API_KEY=legacy-test-key\n')
            with patch.dict(os.environ, {}, clear=True):
                load_environment(root)
                self.assertEqual(os.environ['ELEVENLABS_API_KEY'], 'legacy-test-key')
