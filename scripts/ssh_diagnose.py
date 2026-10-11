"""OpenSSH transport for a bounded Linux diagnostic; does not authorize commands."""

import argparse
import base64
import json
import re
import subprocess
import sys
from pathlib import Path

from remote_runner import validate_request


def build_ssh(host, port=None):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.@-]{0,253}', host):
        raise ValueError('Use an SSH alias or hostname, not an option or URL')
    if port is not None and not 1 <= port <= 65535:
        raise ValueError('Invalid port')
    source = Path(__file__).with_name('remote_runner.py').read_bytes()
    encoded = base64.b64encode(source).decode('ascii')
    # Only reviewed code appears in the remote shell; user argv travels on stdin.
    command = 'python3 -c "import base64;exec(compile(base64.b64decode(\'{}\'),\'<remote-runner>\',\'exec\'))"'.format(encoded)
    args = ['ssh', '-T', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
            '-o', 'ConnectTimeout=10', '-o', 'ServerAliveInterval=5',
            '-o', 'ServerAliveCountMax=2', '-o', 'ClearAllForwardings=yes',
            '-o', 'ControlMaster=no', '-o', 'ControlPath=none',
            '-o', 'PermitLocalCommand=no', '-o', 'RequestTTY=no']
    if port is not None:
        args.extend(['-p', str(port)])
    return args + [host, command]


def receipt_exit(receipt):
    if receipt.get('protocol') != 1:
        return 2
    if not receipt.get('group_cleanup_confirmed'):
        return 126
    reason = receipt.get('reason')
    if reason == 'completed':
        return 0 if receipt.get('command_exit') == 0 else 1
    return {'deadline': 124, 'output_limit': 125, 'interrupted': 130}.get(reason, 2)


def execute(host, request, port=None):
    request = validate_request(request)
    command = build_ssh(host, port)
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        stdout, stderr = process.communicate(
            (json.dumps(request) + '\n').encode(), timeout=request['seconds'] + request['grace'] + 25)
    except (subprocess.TimeoutExpired, KeyboardInterrupt) as error:
        process.kill()
        process.communicate()
        return {'protocol': 1, 'reason': 'client_interrupted' if isinstance(error, KeyboardInterrupt) else 'transport_timeout',
                'group_cleanup_confirmed': False,
                'note': 'Remote cleanup unconfirmed; wait for remote deadline and verify before retrying.'}, 130 if isinstance(error, KeyboardInterrupt) else 2
    if process.returncode != 0:
        return {'protocol': 1, 'reason': 'transport_failure', 'group_cleanup_confirmed': False,
                'note': 'SSH/runner failed. Raw transport output suppressed; check authentication and verified host keys.'}, 2
    try:
        if len(stdout) > request['max_bytes'] * 16 + 8192:
            raise ValueError('Invalid receipt size')
        receipt = json.loads(stdout)
        if not isinstance(receipt, dict):
            raise ValueError('Invalid receipt')
        return receipt, receipt_exit(receipt)
    except (ValueError, UnicodeError):
        return {'protocol': 1, 'reason': 'invalid_receipt', 'group_cleanup_confirmed': False}, 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', required=True)
    parser.add_argument('--port', type=int)
    parser.add_argument('--seconds', type=float, default=15)
    parser.add_argument('--grace', type=float, default=0.5)
    parser.add_argument('--max-bytes', type=int, default=65536)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    argv = args.command[1:] if args.command[:1] == ['--'] else args.command
    try:
        receipt, code = execute(args.host, {'argv': argv, 'seconds': args.seconds,
                                          'grace': args.grace, 'max_bytes': args.max_bytes}, args.port)
    except (ValueError, OSError):
        print('Invalid request or unavailable SSH; no raw command/credential output.', file=sys.stderr)
        return 2
    print(json.dumps(receipt, ensure_ascii=True, indent=2))
    return code


if __name__ == '__main__':
    sys.exit(main())
