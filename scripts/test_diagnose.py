import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from remote_runner import active_group, proc_identity, run_guardian, validate_request
from ssh_diagnose import build_ssh, execute, receipt_exit


class ContractTests(unittest.TestCase):
    def test_request_limits(self):
        for change in ({'seconds': 0}, {'seconds': float('nan')}, {'grace': 8},
                       {'max_bytes': True}, {'max_bytes': 262145}, {'argv': []},
                       {'argv': ['x\0y']}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_request(dict({'argv': ['true']}, **change))

    def test_transport_has_verified_keys_and_no_user_shell_interpolation(self):
        args = build_ssh('approved-alias', 2222)
        self.assertIn('BatchMode=yes', args)
        self.assertIn('StrictHostKeyChecking=yes', args)
        self.assertIn('ClearAllForwardings=yes', args)
        self.assertIn('ControlPath=none', args)
        self.assertNotIn('secret', args[-1])
        for host in ('-oProxyCommand=bad', 'name;whoami', 'name with space', 'https://host'):
            with self.assertRaises(ValueError):
                build_ssh(host)

    def test_exit_contract(self):
        for reason, code in [('deadline', 124), ('output_limit', 125), ('interrupted', 130), ('runner_error', 2)]:
            self.assertEqual(receipt_exit({'protocol': 1, 'reason': reason, 'group_cleanup_confirmed': True}), code)
        self.assertEqual(receipt_exit({'protocol': 1, 'reason': 'completed', 'command_exit': 0,
                                       'group_cleanup_confirmed': True}), 0)
        self.assertEqual(receipt_exit({'protocol': 1, 'group_cleanup_confirmed': False}), 126)

    @patch('ssh_diagnose.subprocess.Popen')
    def test_command_sent_as_stdin_json(self, popen):
        child = popen.return_value
        child.returncode = 0
        child.communicate.return_value = (b'{"protocol":1,"reason":"completed","command_exit":0,"group_cleanup_confirmed":true}', b'')
        request = {'argv': ['echo', 'literal; $(touch unexpected)']}
        receipt, code = execute('approved-alias', request)
        self.assertEqual(code, 0)
        wire = child.communicate.call_args.args[0]
        self.assertEqual(json.loads(wire)['argv'], request['argv'])
        self.assertNotIn(request['argv'][1], popen.call_args.args[0][-1])

    @patch('ssh_diagnose.subprocess.Popen')
    def test_transport_timeout_never_claims_cleanup(self, popen):
        child = popen.return_value
        child.communicate.side_effect = [subprocess.TimeoutExpired('ssh', 1), (b'', b'')]
        receipt, code = execute('approved-alias', {'argv': ['true']})
        self.assertEqual(code, 2)
        self.assertFalse(receipt['group_cleanup_confirmed'])
        child.kill.assert_called_once()

    @patch('ssh_diagnose.subprocess.Popen')
    def test_raw_failure_and_invalid_receipt_are_not_leaked(self, popen):
        child = popen.return_value
        child.returncode = 255
        child.communicate.return_value = (b'', b'private transport output')
        receipt, code = execute('approved-alias', {'argv': ['true']})
        self.assertEqual(code, 2)
        self.assertNotIn('private transport', json.dumps(receipt))
        child.returncode = 0
        child.communicate.return_value = (b'bad response', b'')
        self.assertEqual(execute('approved-alias', {'argv': ['true']})[1], 2)


@unittest.skipUnless(sys.platform == 'linux', 'Linux process groups and /proc required')
class LinuxIntegrationTests(unittest.TestCase):
    def run_code(self, code, **options):
        result = run_guardian(dict({'argv': [sys.executable, '-c', code], 'seconds': 2,
                                   'grace': 0.2, 'max_bytes': 4096}, **options))
        self.assertTrue(result['group_cleanup_confirmed'], result)
        self.assertFalse(active_group(result['group_id']))
        return result

    def test_normal_output_both_streams_and_nonzero_exit(self):
        result = self.run_code('import sys; print("out"); print("err",file=sys.stderr); sys.exit(7)')
        self.assertEqual(result['reason'], 'completed')
        self.assertEqual(result['command_exit'], 7)
        self.assertEqual(result['stdout'], 'out\n')
        self.assertEqual(result['stderr'], 'err\n')

    def test_deadline_kills_term_ignoring_command(self):
        result = self.run_code('import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(60)', seconds=1)
        self.assertEqual(result['reason'], 'deadline')
        self.assertLess(result['seconds_elapsed'], 4)

    def test_output_flood_stops_and_caps_both_streams(self):
        result = self.run_code('import os\nwhile True:\n os.write(1,b"x"*8192); os.write(2,b"y"*8192)', max_bytes=128)
        self.assertEqual(result['reason'], 'output_limit')
        self.assertLessEqual(len(result['stdout']), 128)
        self.assertLessEqual(len(result['stderr']), 128)

    def test_successful_parent_does_not_leave_background_child(self):
        result = self.run_code('import subprocess,sys; subprocess.Popen([sys.executable,"-c","import time; time.sleep(60)"]); print("parent done")')
        self.assertEqual(result['reason'], 'completed')
        self.assertIn('parent done', result['stdout'])

    def test_missing_command_is_a_failure_not_a_hang(self):
        result = run_guardian({'argv': ['not-an-installed-command-fixture'], 'seconds': 2, 'grace': 0.2})
        self.assertEqual(result['command_exit'], 127)
        self.assertTrue(result['group_cleanup_confirmed'])

    def test_full_relay_produces_a_valid_receipt(self):
        request = {'argv': [sys.executable, '-c', 'print("relay verified")'],
                   'seconds': 2, 'grace': 0.2}
        completed = subprocess.run([sys.executable, str(Path(__file__).with_name('remote_runner.py'))],
                                   input=(json.dumps(request) + '\n').encode(),
                                   capture_output=True, timeout=6)
        self.assertEqual(completed.returncode, 0)
        receipt = json.loads(completed.stdout)
        self.assertEqual(receipt_exit(receipt), 0)
        self.assertEqual(receipt['stdout'], 'relay verified\n')

    def test_lost_relay_does_not_cancel_remote_deadline(self):
        with tempfile.TemporaryDirectory(prefix='server-ops-test-') as root:
            marker = Path(root) / 'command.pid'
            code = 'import os,time; from pathlib import Path; Path({!r}).write_text(str(os.getpid())); time.sleep(60)'.format(str(marker))
            relay = subprocess.Popen([sys.executable, str(Path(__file__).with_name('remote_runner.py'))],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                relay.stdin.write((json.dumps({'argv': [sys.executable, '-c', code], 'seconds': 1, 'grace': 0.2}) + '\n').encode())
                relay.stdin.close()
                until = time.monotonic() + 3
                while not marker.exists() and time.monotonic() < until:
                    time.sleep(0.02)
                self.assertTrue(marker.exists())
                pid = int(marker.read_text())
                identity = proc_identity(pid)
                self.assertIsNotNone(identity)
                relay.kill()
                relay.wait(timeout=2)
                until = time.monotonic() + 4
                while active_group(identity['group']) and time.monotonic() < until:
                    time.sleep(0.05)
                self.assertFalse(active_group(identity['group']))
            finally:
                if relay.poll() is None:
                    relay.kill()
                    relay.wait()
                relay.stdout.close()
                relay.stderr.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
