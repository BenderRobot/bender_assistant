import ctypes
import os
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

from bender_voice.processes import process_exists


class ProcessTests(unittest.TestCase):
    def test_current_worker_and_invalid_identifiers_never_send_a_signal(self):
        with patch('bender_voice.processes.os.kill', side_effect=AssertionError('signal forbidden')):
            self.assertTrue(process_exists(os.getpid()))
            for pid in (None, 0, -1, True, '123'):
                self.assertFalse(process_exists(pid))

    def test_windows_checks_a_wait_handle_and_always_closes_it(self):
        kernel = Mock()
        kernel.OpenProcess.return_value = 456
        with patch('bender_voice.processes.os.name', 'nt'), \
             patch.object(ctypes, 'WinDLL', return_value=kernel, create=True), \
             patch('bender_voice.processes.os.kill', side_effect=AssertionError('signal forbidden')):
            for wait_result, expected in ((258, True), (0, False), (0xFFFFFFFF, True)):
                kernel.WaitForSingleObject.return_value = wait_result
                self.assertEqual(process_exists(123), expected)
                kernel.OpenProcess.assert_called_with(0x00100000, False, 123)
            self.assertEqual(kernel.CloseHandle.call_count, 3)

    def test_windows_unknown_permissions_do_not_start_a_duplicate_worker(self):
        kernel = Mock()
        kernel.OpenProcess.return_value = None
        with patch('bender_voice.processes.os.name', 'nt'), \
             patch.object(ctypes, 'WinDLL', return_value=kernel, create=True), \
             patch.object(ctypes, 'get_last_error', create=True) as error:
            error.return_value = 87
            self.assertFalse(process_exists(123))
            error.return_value = 5
            self.assertTrue(process_exists(123))
            kernel.CloseHandle.assert_not_called()

    def test_real_child_survives_the_probe_and_exit_is_detected(self):
        child = subprocess.Popen([sys.executable, '-c', 'import sys; sys.stdin.read()'], stdin=subprocess.PIPE)
        try:
            self.assertTrue(process_exists(child.pid))
            self.assertIsNone(child.poll())
            child.stdin.close()
            self.assertEqual(child.wait(timeout=5), 0)
            self.assertFalse(process_exists(child.pid))
        finally:
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=5)
