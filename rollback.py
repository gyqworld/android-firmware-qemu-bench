"""Stop only this project's VM and verify its privately supplied source images."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
from config import ROOT


def rollback(stop=True):
    outcome = {'stopped_pid': None, 'sources_unchanged': {}}
    session = ROOT / 'output/session.json'
    if session.exists():
        info = json.loads(session.read_text())
        pid = int(info['qemu_pid'])
        p = subprocess.run(['powershell', '-NoProfile', '-Command',
            f"Get-CimInstance Win32_Process -Filter 'ProcessId = {pid}' | Select-Object Name,CommandLine | ConvertTo-Json -Compress"], capture_output=True, text=True)
        if p.returncode:
            raise RuntimeError('Process identity query failed')
        if p.stdout.strip():
            found = json.loads(p.stdout)
            if found['Name'] != 'qemu-system-aarch64.exe' or str(ROOT / 'output') not in (found.get('CommandLine') or ''):
                raise RuntimeError('Recorded PID belongs to a different process; it was left running')
            output = Path(info['output']).resolve()
            if ROOT / 'output' not in output.parents:
                raise ValueError('Session output is not inside this project')
            if stop:
                p = subprocess.run(['powershell', '-NoProfile', '-Command', f'Stop-Process -Id {pid} -ErrorAction Stop'], capture_output=True, text=True)
                if p.returncode:
                    raise RuntimeError(p.stderr)
                outcome['stopped_pid'] = pid
    manifest_path = ROOT / 'original-sources.local.json'
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        for name, row in manifest['files'].items():
            p = Path(manifest['firmware_dir']) / name
            with p.open('rb') as f:
                value = hashlib.file_digest(f, 'sha256').hexdigest()
            outcome['sources_unchanged'][name] = p.stat().st_size == row['bytes'] and value == row['sha256']
        if not all(outcome['sources_unchanged'].values()):
            raise ValueError('A source image differs from the recorded baseline')
    (ROOT / 'output').mkdir(exist_ok=True)
    (ROOT / 'output/rollback-verification.local.json').write_text(json.dumps(outcome, indent=2) + '\n')
    print('PASS source integrity; ' + ('test VM stopped or absent' if stop else 'verification only; VM unchanged') + '; persistent app data retained')
    return outcome


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--verify-only', action='store_true')
    rollback(not parser.parse_args().verify_only)
