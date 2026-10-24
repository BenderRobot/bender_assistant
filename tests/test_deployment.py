import io
import json
from pathlib import Path
import runpy
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
verifier = runpy.run_path(str(ROOT / 'scripts/verify-deployment.py'))
verify = verifier['verify']
REVISION = 'a' * 40


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.responses = {
            '/api/system/version': {'ui_version': verifier['UI_VERSION'], 'revision': REVISION},
            '/openapi.json': {'paths': {path: {} for path in (
                '/api/media/{identifier}/reference', '/api/bulletins', '/api/voice/live-settings')}},
            '/static/bulletins.js': '/api/bulletins/play',
            '/api/voice/status': {'cloud_integration': 'sdk-with-timestamps-v1', 'cloud_sdk_installed': True},
            '/': '<aside class="workspace-sidebar"><p id="deploymentVersion"></p></aside>'
                 '<h2 id="actualVoiceName"></h2><script src="/static/voice-status.js"></script>',
            '/static/voice-status.js': 'BenderVoiceStatus',
        }

    def open(self, url, **kwargs):
        value = self.responses[url.removeprefix('http://test')]
        return io.BytesIO((value if isinstance(value, str) else json.dumps(value)).encode())

    def test_accepts_only_the_expected_running_revision_and_current_ui(self):
        with patch.dict(verify.__globals__, urlopen=self.open):
            self.assertEqual(verify('http://test', REVISION)['revision'], REVISION)
            self.responses['/api/system/version']['revision'] = 'b' * 40
            with self.assertRaisesRegex(ValueError, 'Revision'):
                verify('http://test', REVISION)
            self.responses['/api/system/version']['revision'] = REVISION
            self.responses['/api/system/version']['ui_version'] = 'old'
            with self.assertRaisesRegex(ValueError, 'Interface'):
                verify('http://test', REVISION)

    def test_old_assets_or_missing_sdk_prevent_success_even_with_http_200(self):
        with patch.dict(verify.__globals__, urlopen=self.open):
            self.responses['/'] = '<h2 id="actualVoiceName"></h2>/static/voice-status.js'
            with self.assertRaisesRegex(ValueError, 'workspace-sidebar'):
                verify('http://test', REVISION)
            self.responses['/api/voice/status']['cloud_sdk_installed'] = False
            with self.assertRaisesRegex(ValueError, 'SDK'):
                verify('http://test', REVISION)

    def test_public_identity_reveals_no_environment_values_and_rejects_invalid_revision(self):
        for revision, expected in ((REVISION, REVISION), ('not-a-commit', None), ('', None)):
            with patch.dict('os.environ', {'BENDER_REVISION': revision, 'ELEVENLABS_API_KEY': 'secret-test-value'}):
                module = runpy.run_path(str(ROOT / 'build_info.py'))
                result = module['build_info']()
            self.assertEqual(result['revision'], expected)
            self.assertEqual(set(result), {'revision', 'ui_version'})
            self.assertNotIn('secret-test-value', json.dumps(result))
