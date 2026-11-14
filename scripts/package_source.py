"""Create a source ZIP from reviewed paths, never the working directory."""
from pathlib import Path
import argparse
import hashlib
import json
import zipfile
from audit_public import ROOT, audit


def package(target):
    result = audit(require_index=True)
    if not result['passed']:
        raise ValueError('\n'.join(result['errors']))
    target = Path(target).resolve()
    if target in [ROOT / row['path'] for row in result['files']]:
        raise ValueError('Archive would overwrite source')
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for row in result['files']:
            info = zipfile.ZipInfo('android-firmware-qemu-bench/' + row['path'], date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            z.writestr(info, (ROOT / row['path']).read_bytes())
    with zipfile.ZipFile(target) as z:
        expected = {'android-firmware-qemu-bench/' + row['path']: row['sha256'] for row in result['files']}
        if set(z.namelist()) != set(expected):
            raise ValueError('Release inventory mismatch')
        for name, digest in expected.items():
            if hashlib.sha256(z.read(name)).hexdigest() != digest:
                raise ValueError('Release member mismatch: ' + name)
    report = {'archive': str(target), 'bytes': target.stat().st_size,
        'sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'members': len(result['files']),
        'source_only': True, 'firmware_included': False, 'apk_included': False}
    target.with_suffix('.local.json').write_text(json.dumps(report, indent=2) + '\n')
    print('PASS reopened source archive:', target, report['members'], 'files')
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, default=ROOT / 'reports/source-release.zip')
    package(p.parse_args().output)
