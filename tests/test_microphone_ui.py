from pathlib import Path
import shutil
import subprocess
import unittest


class MicrophoneUITests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node facultatif pour les tests du contrôleur web')
    def test_record_pause_transcribe_and_reply_flow(self):
        result = subprocess.run([shutil.which('node'), str(Path(__file__).with_name('microphone-ui.cjs'))],
                                capture_output=True, text=True, encoding='utf-8', timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
