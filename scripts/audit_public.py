"""Fail-closed audit of the actual Git index and source-release allowlist."""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'scripts/public-files.json'
MAGICS = (b'\x7fELF', b'MZ', b'PK\x03\x04', b'ANDROID!', b'\x1f\x8b', b'hsqs', b'\x3a\xff\x26\xed', b'dex\n')
PRIVATE_PARTS = {'local', 'runtime', 'build', 'data', 'output', 'reports', 'original', 'modified', 'changes', 'cache', '.venv', '__pycache__'}
PRIVATE_SUFFIXES = {'.apk', '.img', '.so', '.dll', '.exe', '.o', '.a', '.bin', '.jar', '.dex', '.odex', '.vdex', '.zip', '.gz', '.zst', '.key', '.pem'}
PATTERNS = {
    'private-user-path': rb'(?i)(?:[a-z]:[\\/]+Users[\\/]+(?!PUBLIC[\\/]))|(?:[a-z]:[\\/]+baidunetdiskdownload[\\/])',
    'private-key': rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
    'credential': rb'(?i)(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|AKIA[A-Z0-9]{16})',
}


def public_files():
    rows = json.loads(MANIFEST.read_text(encoding='utf8'))['files']
    if len(rows) != len(set(rows)):
        raise ValueError('Duplicate public paths')
    for name in rows:
        p = PurePosixPath(name)
        if p.is_absolute() or '..' in p.parts or '\\' in name:
            raise ValueError('Invalid public path: ' + name)
        if set(x.lower() for x in p.parts) & PRIVATE_PARTS or p.suffix.lower() in PRIVATE_SUFFIXES:
            raise ValueError('Private/generated path in public manifest: ' + name)
    return rows


def check_bytes(name, data):
    errors = []
    p = PurePosixPath(name)
    if set(x.lower() for x in p.parts) & PRIVATE_PARTS or p.suffix.lower() in PRIVATE_SUFFIXES:
        errors.append(name + ': private/generated path')
    if len(data) > 1024 * 1024:
        errors.append(name + ': exceeds source-size limit')
    if data.startswith(MAGICS) or b'\0' in data:
        errors.append(name + ': binary signature or NUL')
    try:
        data.decode('utf8')
    except UnicodeDecodeError:
        errors.append(name + ': not UTF-8 source')
    for label, pattern in PATTERNS.items():
        if re.search(pattern, data):
            errors.append(name + ': ' + label)
    return errors


def audit(require_index=False):
    allowed = set(public_files())
    errors, rows, indexed = [], [], []
    for name in sorted(allowed):
        p = ROOT / name
        if not p.is_file() or p.is_symlink():
            errors.append(name + ': missing/non-regular/symlink')
            continue
        data = p.read_bytes()
        errors.extend(check_bytes(name, data))
        rows.append({'path': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
    git = subprocess.run(['git', 'ls-files', '--stage', '-z'], cwd=ROOT, capture_output=True)
    if git.returncode == 0:
        for raw in git.stdout.split(b'\0'):
            if not raw:
                continue
            metadata, namebytes = raw.split(b'\t', 1)
            mode, oid, stage = metadata.decode().split()
            name = namebytes.decode('utf8')
            indexed.append(name)
            if name not in allowed:
                errors.append(name + ': unexpected Git-index path')
            if mode not in ('100644', '100755') or stage != '0':
                errors.append(name + ': unexpected index mode/stage')
            blob = subprocess.run(['git', 'cat-file', 'blob', oid], cwd=ROOT, capture_output=True)
            if blob.returncode:
                errors.append(name + ': indexed blob unreadable')
            else:
                errors.extend(check_bytes(name, blob.stdout))
        if require_index and set(indexed) != allowed:
            errors.append('Git index differs from reviewed source manifest')
    elif require_index:
        errors.append('No Git index')
    return {'passed': not errors, 'errors': errors, 'files': rows, 'indexed_files': indexed,
        'firmware_included': False, 'apk_included': False, 'runtime_binaries_included': False}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--require-index', action='store_true')
    p.add_argument('--json', type=Path)
    args = p.parse_args()
    result = audit(args.require_index)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, indent=2) + '\n')
    print(('PASS' if result['passed'] else 'FAIL') + ': ' + str(len(result['files'])) + ' reviewed source files')
    for error in result['errors']:
        print(error)
    raise SystemExit(0 if result['passed'] else 1)
