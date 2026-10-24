"""Exercise the repair shell script in the actual extracted archive layout."""
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
FILES=('media_api.py','bender_voice/config.py','bender_voice/service.py',
       'bender_voice/references.py','static/media.js','templates/index.html',
       'scripts/repair-reference-ui.sh')


def bash_path():
    binary=shutil.which('bash')
    if binary:return binary
    git=shutil.which('git')
    if git:
        candidate=Path(git).resolve().parents[1]/'bin'/'bash.exe'
        if candidate.is_file():return str(candidate)
    return None


@unittest.skipUnless(bash_path(),'Bash requis pour tester le paquet de réparation')
class ReferenceRepairTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        archive=self.root/'payload.tar.gz'
        with tarfile.open(archive,'w:gz') as bundle:
            for name in FILES:bundle.add(ROOT/name,arcname=name)
        self.stage=self.root/'extracted';self.stage.mkdir()
        with tarfile.open(archive) as bundle:bundle.extractall(self.stage,filter='data')

    def check(self):
        return subprocess.run([bash_path(),'--noprofile','--norc',
                               str(self.stage/'scripts'/'repair-reference-ui.sh'),'--check-payload'],
                              capture_output=True,text=True,timeout=20)

    def test_payload_is_found_above_the_scripts_directory(self):
        result=self.check()
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('Payload files verified',result.stdout)
        # Payload validation requires neither an installed application nor sudo.
        self.assertNotIn('Application:',result.stdout)

    def test_incomplete_payload_reports_the_missing_file(self):
        (self.stage/'static'/'media.js').unlink()
        result=self.check()
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Repair payload file missing:',result.stderr)
        self.assertIn('static/media.js',result.stderr)
