"""Prepare only the pinned public ARM64 kernel; never download vehicle firmware."""
from pathlib import Path
import base64
import gzip
import hashlib
import json
import urllib.request
from config import ROOT, load

URL = 'https://android.googlesource.com/platform/prebuilts/qemu-kernel/+/refs/heads/emu-29.0-release/arm64/4.14/kernel-qemu2?format=TEXT'
BLOB = '5b5c6a2754da58a22de40b2c62399d935db0ebad'
SHA256 = 'bf470d9ffecf50cdd114ebb6d5dc4a82e5b21593cf328900efcb4ce8d70dfe9f'
IMAGE_SHA256 = '2f58cf29b0eb458638289d5ae8c8097c6daa66547a93f43eb09d3f3769f7c202'


def prepare(offline=False):
    target = Path(load()['kernel'])
    if target.exists():
        if hashlib.sha256(target.read_bytes()).hexdigest() != IMAGE_SHA256:
            raise ValueError('Configured kernel differs from the pinned image; existing file preserved')
        print('Reused verified Android-capable ARM64 kernel')
        return
    if offline:
        raise FileNotFoundError('Offline kernel cache missing')
    with urllib.request.urlopen(URL, timeout=60) as response:
        data = base64.b64decode(b''.join(response.read(64 * 1024 * 1024).split()), validate=True)
    if hashlib.sha256(data).hexdigest() != SHA256 or hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() != BLOB:
        raise ValueError('Kernel source object digest mismatch')
    kernel = gzip.decompress(data)
    if hashlib.sha256(kernel).hexdigest() != IMAGE_SHA256:
        raise ValueError('Expanded kernel digest mismatch')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(kernel)
    report = ROOT / 'reports/kernel-source.local.json'
    report.parent.mkdir(exist_ok=True)
    report.write_text(json.dumps({'url': URL, 'git_blob_sha1': BLOB, 'compressed_sha256': SHA256,
        'image_sha256': IMAGE_SHA256, 'source_url': 'https://android.googlesource.com/kernel/goldfish/+/c9f068b0fccc/'}, indent=2) + '\n')
    print('Prepared verified public kernel; original Exynos boot.img not used')


if __name__ == '__main__':
    prepare()
