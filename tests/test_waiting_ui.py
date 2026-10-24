from pathlib import Path
import shutil
import subprocess
import unittest


class WaitingUITests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node facultatif pour les tests web')
    def test_parallel_preparation_handoff_and_cancellation(self):
        result = subprocess.run([shutil.which('node'), str(Path(__file__).with_name('waiting-ui.cjs'))],
                                capture_output=True, text=True, encoding='utf-8', timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
