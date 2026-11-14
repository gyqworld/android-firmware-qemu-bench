"""Local input paths. Nothing in this module locates or downloads firmware."""
from pathlib import Path
import json
import os

ROOT = Path(__file__).resolve().parent
DEFAULTS = {
    'firmware_dir': 'local/firmware',
    'qemu': 'runtime/msys2/ucrt64/bin/qemu-system-aarch64.exe',
    'initramfs': 'runtime/alpine/initramfs-virt',
    'kernel': 'runtime/kernel/Image-4.14',
    'node': 'node', 'clang': 'clang', 'linker': 'ld.lld',
}


def load(path=None):
    source = Path(path or os.environ.get('ANDROID_BENCH_CONFIG', ROOT / 'config.local.json')).resolve()
    raw = json.loads(source.read_text(encoding='utf-8-sig')) if source.exists() else {}
    unknown = set(raw) - set(DEFAULTS)
    if unknown:
        raise ValueError('Unknown configuration keys: ' + ', '.join(sorted(unknown)))
    values = dict(DEFAULTS, **raw)
    for name, value in values.items():
        if not isinstance(value, str) or not value.strip():
            raise ValueError('Missing path: ' + name)
        if name in ('node', 'clang', 'linker') and not any(c in value for c in ('/', '\\')):
            continue
        p = Path(os.path.expandvars(value)).expanduser()
        values[name] = str(p.resolve() if p.is_absolute() else (source.parent / p).resolve())
    return values


def save_new(path, values):
    """Never silently overwrite a user's existing configuration."""
    path = Path(path)
    if path.exists():
        return False
    path.write_text(json.dumps(values, indent=2) + '\n', encoding='utf-8')
    return True
