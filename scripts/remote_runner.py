"""Linux-only remote diagnostic guardian, sent over SSH without installing a file."""

import json
import math
import os
import selectors
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path


LEADER = r'''
import json, os, signal, subprocess, sys
signal.signal(signal.SIGTERM, signal.SIG_IGN)
signal.signal(signal.SIGHUP, signal.SIG_IGN)
status_fd, control_fd = map(int, sys.argv[1:])
argv = json.loads(sys.stdin.readline())
def reset_signals():
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    signal.signal(signal.SIGHUP, signal.SIG_DFL)
try:
    child = subprocess.Popen(argv, stdin=subprocess.DEVNULL, preexec_fn=reset_signals,
                             close_fds=True)
    code = child.wait()
except Exception:
    code = 127
os.write(status_fd, (str(code) + "\n").encode())
os.close(status_fd)
# Stay alive to reserve this session/group ID until the guardian finishes cleanup.
while os.read(control_fd, 1):
    pass
'''


def validate_request(request):
    if not isinstance(request, dict):
        raise ValueError('Request must be an object')
    argv = request.get('argv')
    if (not isinstance(argv, list) or not argv or len(argv) > 128 or
            any(not isinstance(item, str) or '\0' in item for item in argv) or
            not argv[0] or sum(len(item) for item in argv) > 32768):
        raise ValueError('Invalid argv')
    seconds = request.get('seconds', 15)
    grace = request.get('grace', 0.5)
    limit = request.get('max_bytes', 65536)
    for value, low, high in [(seconds, 1, 120), (grace, 0.2, 5)]:
        if (isinstance(value, bool) or not isinstance(value, (int, float)) or
                not math.isfinite(value) or not low <= value <= high):
            raise ValueError('Invalid time bound')
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 262144:
        raise ValueError('Invalid output bound')
    return {'argv': argv, 'seconds': seconds, 'grace': grace, 'max_bytes': limit}


def proc_identity(pid):
    try:
        fields = Path('/proc/{}/stat'.format(pid)).read_text().rsplit(')', 1)[1].split()
        return {'state': fields[0], 'group': int(fields[2]), 'start': int(fields[19])}
    except (FileNotFoundError, ProcessLookupError):
        return None


def active_group(group):
    members = []
    for entry in Path('/proc').iterdir():
        if entry.name.isdigit():
            identity = proc_identity(int(entry.name))
            if identity and identity['group'] == group and identity['state'] not in ('Z', 'X'):
                members.append(int(entry.name))
    return members


def run_guardian(request):
    request = validate_request(request)
    if sys.platform != 'linux':
        raise RuntimeError('Linux /proc is required')
    interrupted = [False]
    old_term = signal.signal(signal.SIGTERM, lambda *_: interrupted.__setitem__(0, True))
    old_hup = signal.signal(signal.SIGHUP, signal.SIG_IGN)
    status_read, status_write = os.pipe()
    control_read, control_write = os.pipe()
    process = None
    selector = selectors.DefaultSelector()
    outputs = {'stdout': bytearray(), 'stderr': bytearray()}
    reason = 'runner_error'
    command_exit = None
    identity = None
    cleanup = False
    escalated = False
    start = time.monotonic()
    status_data = bytearray()
    try:
        process = subprocess.Popen(
            [sys.executable, '-c', LEADER, str(status_write), str(control_read)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            start_new_session=True, pass_fds=(status_write, control_read), close_fds=True)
        os.close(status_write)
        status_write = None
        os.close(control_read)
        control_read = None
        identity = proc_identity(process.pid)
        if not identity or identity['group'] != process.pid:
            raise RuntimeError('Cannot establish owned session')
        process.stdin.write((json.dumps(request['argv']) + '\n').encode())
        process.stdin.close()
        for stream, label in [(process.stdout, 'stdout'), (process.stderr, 'stderr'), (status_read, 'status')]:
            fd = stream if isinstance(stream, int) else stream.fileno()
            os.set_blocking(fd, False)
            selector.register(fd, selectors.EVENT_READ, label)
        while True:
            if interrupted[0]:
                reason = 'interrupted'
                break
            if time.monotonic() - start >= request['seconds']:
                reason = 'deadline'
                break
            if process.poll() is not None:
                reason = 'leader_lost'
                break
            for key, _ in selector.select(min(0.05, request['seconds'])):
                chunk = os.read(key.fd, 16384)
                if not chunk:
                    selector.unregister(key.fd)
                    continue
                if key.data == 'status':
                    status_data.extend(chunk)
                    if b'\n' in status_data:
                        command_exit = int(status_data.split(b'\n')[0])
                else:
                    available = request['max_bytes'] - len(outputs[key.data])
                    outputs[key.data].extend(chunk[:available])
                    if len(chunk) > available:
                        reason = 'output_limit'
            if reason == 'output_limit':
                break
            if command_exit is not None:
                reason = 'completed'
                break
    finally:
        if process:
            # The leader ignores TERM and reserves its ID through this final KILL.
            current = proc_identity(process.pid)
            if (process.poll() is None and identity and current and
                    current['start'] == identity['start'] and current['group'] == process.pid):
                os.killpg(process.pid, signal.SIGTERM)
                time.sleep(request['grace'])
                current = proc_identity(process.pid)
                if (process.poll() is None and current and current['start'] == identity['start']):
                    os.killpg(process.pid, signal.SIGKILL)
                    escalated = True
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    pass
                until = time.monotonic() + 1
                while time.monotonic() < until:
                    if not active_group(process.pid):
                        cleanup = True
                        break
                    time.sleep(0.02)
            # Pipes are bounded in size; drain remaining output only for a short interval.
            until = time.monotonic() + 0.2
            while selector.get_map() and time.monotonic() < until:
                for key, _ in selector.select(0.02):
                    chunk = os.read(key.fd, 16384)
                    if not chunk:
                        selector.unregister(key.fd)
                    elif key.data in outputs:
                        available = request['max_bytes'] - len(outputs[key.data])
                        outputs[key.data].extend(chunk[:available])
                        if len(chunk) > available:
                            reason = 'output_limit'
            for stream in (process.stdout, process.stderr):
                stream.close()
        selector.close()
        for fd in (status_read, status_write, control_read, control_write):
            if fd is not None:
                os.close(fd)
        signal.signal(signal.SIGTERM, old_term)
        signal.signal(signal.SIGHUP, old_hup)
    return {
        'protocol': 1, 'job_id': str(uuid.uuid4()), 'reason': reason,
        'command_exit': command_exit, 'seconds_elapsed': round(time.monotonic() - start, 3),
        'group_id': process.pid if process else None,
        'group_start_ticks': identity['start'] if identity else None,
        'group_cleanup_confirmed': cleanup, 'final_group_kill': escalated,
        'stdout': outputs['stdout'].decode('utf-8', errors='replace'),
        'stderr': outputs['stderr'].decode('utf-8', errors='replace'),
        'scope': 'owned-process-group-only',
    }


def main():
    if sys.platform != 'linux':
        raise RuntimeError('Linux /proc is required')
    raw = sys.stdin.buffer.readline(65537)
    if len(raw) > 65536 or not raw.endswith(b'\n'):
        raise ValueError('Invalid request size')
    request = validate_request(json.loads(raw))
    result_read, result_write = os.pipe()
    guardian = os.fork()
    if guardian == 0:
        os.close(result_read)
        os.setsid()
        # Detach inherited SSH channel descriptors; only the receipt pipe is retained.
        null = os.open(os.devnull, os.O_RDWR)
        for fd in (0, 1, 2):
            os.dup2(null, fd)
        if null > 2:
            os.close(null)
        try:
            result = run_guardian(request)
            payload = (json.dumps(result, ensure_ascii=True) + '\n').encode()
            offset = 0
            while offset < len(payload):
                offset += os.write(result_write, payload[offset:])
        except BrokenPipeError:
            pass
        except Exception:
            try:
                os.write(result_write, b'{"protocol":1,"reason":"runner_error","group_cleanup_confirmed":false}\n')
            except BrokenPipeError:
                pass
        finally:
            os.close(result_write)
        os._exit(0)
    os.close(result_write)
    try:
        while True:
            chunk = os.read(result_read, 16384)
            if not chunk:
                break
            sys.stdout.buffer.write(chunk)
            sys.stdout.buffer.flush()
    finally:
        os.close(result_read)
    os.waitpid(guardian, 0)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print('{"protocol":1,"reason":"runner_error","group_cleanup_confirmed":false}')
        sys.exit(2)
