"""Publish a completion receipt only after the whole test suite succeeds."""
import argparse
from contextlib import ExitStack
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, text):
        for stream in self.streams:
            stream.write(text)
            stream.flush()

    def flush(self):
        for stream in self.streams:
            stream.flush()


def run(report, run_id, log=None):
    report.unlink(missing_ok=True)
    suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'))
    expected = suite.countTestCases()
    with ExitStack() as stack:
        stream = sys.stderr
        if log is not None:
            log.parent.mkdir(parents=True, exist_ok=True)
            stream = Tee(stream, stack.enter_context(log.open('w', encoding='utf-8')))
        result = unittest.TextTestRunner(verbosity=2, stream=stream).run(suite)
    if not result.wasSuccessful() or result.testsRun != expected or not expected:
        return 1
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({'run_id': run_id, 'passed': True,
                                  'tests_run': result.testsRun, 'expected': expected}), encoding='utf-8')
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--log', type=Path)
    arguments = parser.parse_args()
    raise SystemExit(run(arguments.report, arguments.run_id, arguments.log))
