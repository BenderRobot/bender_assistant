import json
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]


class TestCompletionTests(unittest.TestCase):
    def test_an_incomplete_or_failed_suite_never_leaves_a_success_receipt(self):
        run = runpy.run_path(str(ROOT / 'scripts/run-tests.py'))['run']
        for passed, count in ((False, 2), (True, 1)):
            with tempfile.TemporaryDirectory() as directory:
                report = Path(directory) / 'tests.json'
                report.write_text('old receipt')
                result = Mock(testsRun=count)
                result.wasSuccessful.return_value = passed
                suite = Mock()
                suite.countTestCases.return_value = 2
                with patch.object(unittest.defaultTestLoader, 'discover', return_value=suite), \
                     patch.object(unittest, 'TextTestRunner') as runner:
                    runner.return_value.run.return_value = result
                    self.assertEqual(run(report, 'run-id'), 1)
                self.assertFalse(report.exists())

    def test_zero_exit_without_finishing_is_not_a_successful_test_run(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / 'tests.json'
            program = '''import os, runpy, sys, unittest
from pathlib import Path
run = runpy.run_path(sys.argv[1])['run']
class Interrupted(unittest.TestCase):
    def runTest(self): os._exit(0)
unittest.defaultTestLoader.discover = lambda *a: unittest.TestSuite([Interrupted()])
run(Path(sys.argv[2]), 'interrupted')
'''
            result = subprocess.run([sys.executable, '-c', program, str(ROOT / 'scripts/run-tests.py'), str(report)],
                                    capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 0)
            self.assertFalse(report.exists())

    def test_complete_success_receipt_contains_the_run_identity_and_test_count(self):
        run = runpy.run_path(str(ROOT / 'scripts/run-tests.py'))['run']
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / 'tests.json'
            log = Path(directory) / 'tests.log'
            suite = unittest.TestSuite([unittest.FunctionTestCase(lambda: None)])
            with patch.object(unittest.defaultTestLoader, 'discover', return_value=suite):
                self.assertEqual(run(report, 'expected-id', log), 0)
            self.assertIn('Ran 1 test', log.read_text(encoding='utf-8'))
            self.assertEqual(json.loads(report.read_text()),
                             {'run_id': 'expected-id', 'passed': True, 'tests_run': 1, 'expected': 1})
