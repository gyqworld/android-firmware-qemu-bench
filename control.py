"""Send a diagnostic command only to this disposable guest's loopback port."""
from pathlib import Path
import argparse
import json
import socket
import re
import shlex
import time
import uuid
import msvcrt

D = Path(__file__).resolve().parent


def main():
    p = argparse.ArgumentParser()
    p.add_argument('command')
    p.add_argument('--timeout', type=int, default=30)
    a = p.parse_args()
    if '\n' in a.command or '\r' in a.command:
        p.error('Use one shell command line')
    # Serialize clients: the guest has exactly one request/reply serial stream.
    lock=(D/'output/control.lock').open('a+b')
    lock.seek(0);lock.write(b'0');lock.flush();lock.seek(0)
    deadline=time.monotonic()+a.timeout+15
    while True:
        try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);break
        except OSError:
            if time.monotonic()>deadline:raise SystemExit('Another diagnostic command is still running')
            time.sleep(.2)
    info = json.loads((D / 'output/session.json').read_text())
    if info['state'] != 'running':
        raise SystemExit('Session ended')
    token = 'BENCH_CMD_DONE_' + uuid.uuid4().hex
    data = bytearray()
    with socket.create_connection(('127.0.0.1', info['control_port']), timeout=10) as s:
        s.settimeout(2)
        time.sleep(2)
        line = '/bench/busybox timeout -s TERM -k 2 '+str(a.timeout)+' /system/bin/sh -c ' + shlex.quote(a.command) + '; status=$?; echo ' + token + ':$status\n'
        s.sendall(line.encode())
        end = time.monotonic() + a.timeout + 10
        while time.monotonic() < end:
            try:
                b = s.recv(65536)
            except socket.timeout:
                continue
            if not b:
                break
            data.extend(b)
            if re.search(re.escape(token.encode()) + rb':\d+\r?\n', data):
                break
    out = Path(info['output']) / ('control-' + time.strftime('%H%M%S') + '.log')
    out.write_bytes(data)
    match = re.search(re.escape(token.encode()) + rb':(\d+)\r?\n', data)
    out.with_suffix('.json').write_text(json.dumps({'command': a.command,
        'guest_exit_status': int(match[1]) if match else None,
        'output': str(out), 'completed': match is not None}, indent=2) + '\n')
    print(data.decode('utf8', 'replace'))
    if match is None:
        raise SystemExit('Diagnostic command did not finish before deadline')
    raise SystemExit(int(match[1]))


if __name__ == '__main__':
    main()
