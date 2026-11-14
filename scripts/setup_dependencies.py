"""Reuse installed tools first; otherwise fetch pinned, public dependencies only."""
import argparse
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'runtime/python-packages'))
from config import DEFAULTS, load
from dependency_utils import Downloader, extract_zip_files, sha256


def discover(value, fallbacks=()):
    for candidate in [value, *fallbacks]:
        if not candidate:
            continue
        path = shutil.which(str(candidate))
        if path:
            return str(Path(path).resolve())
        if Path(candidate).is_file():
            return str(Path(candidate).resolve())
    return None


def python_packages(lock, downloader):
    tag = 'cp' + str(sys.version_info.major) + str(sys.version_info.minor)
    for name, row in lock['python_packages'].items():
        module = 'PIL' if name == 'pillow' else 'zstandard'
        try:
            if importlib.metadata.version(name) == row['version']:
                importlib.import_module(module)
                print('Reused Python package:', name, row['version'])
                continue
        except (ImportError, importlib.metadata.PackageNotFoundError):
            pass
        matches = [s for s in row['wheels'] if ('-' + tag + '-' + tag + '-') in s['filename']]
        if len(matches) != 1:
            raise RuntimeError('No locked wheel for this interpreter; use the portable Python bootstrap')
        spec = matches[0]
        archive = downloader.obtain(spec['filename'], spec)
        extract_zip_files(archive, ROOT / 'runtime/python-packages')
        importlib.invalidate_caches()
        importlib.import_module(module)
        print('Prepared local Python package:', name, row['version'])


def setup(args):
    lock_path = ROOT / 'scripts/dependencies/bootstrap.lock.json'
    lock = json.loads(lock_path.read_text())
    native = json.loads((ROOT / 'scripts/dependencies/windows-x64.lock.json').read_text())
    if args.plan:
        print(json.dumps({'reuse_existing_first': True, 'firmware_downloaded': False, 'apk_downloaded': False,
            'optional_downloads': ['Python 3.11 embeddable (PowerShell bootstrap)', 'Pillow', 'zstandard', 'QEMU/MSYS2 DLL closure',
                'LLVM when missing', 'Node.js when missing', 'Alpine initramfs (BusyBox/musl only)', 'AOSP ARM64 kernel', 'SwiftShader libraries'],
            'qemu_download_bytes_if_missing': sum(native['msys2_packages'][n]['size'] for n in native['qemu_packages']),
            'written_paths': ['runtime/', 'build/', 'reports/', 'config.local.json (new paths only; existing entries preserved)'],
            'no_system_installation': True}, indent=2))
        return 0
    if platform.system() != 'Windows' or platform.machine().lower() not in ('amd64', 'x86_64'):
        raise RuntimeError('Setup currently supports Windows x64; tests and --plan are cross-platform')
    config_file = ROOT / 'config.local.json'
    raw = json.loads(config_file.read_text(encoding='utf-8-sig')) if config_file.exists() else {}
    cfg = load(config_file)
    for name in ('qemu', 'initramfs', 'kernel', 'node', 'clang', 'linker', 'firmware_dir'):
        value = getattr(args, name, None)
        if value:
            raw[name] = str(Path(value).resolve()) if name == 'firmware_dir' or any(c in value for c in ('/', '\\')) else value
    # Only missing entries are auto-filled; user-selected paths are never replaced.
    cfg = dict(cfg)
    for key, value in raw.items():
        if key in ('node', 'clang', 'linker') and not any(c in value for c in ('/', '\\')):
            cfg[key] = value
        else:
            path = Path(value).expanduser()
            cfg[key] = str(path.resolve() if path.is_absolute() else (ROOT / path).resolve())
    downloader = Downloader(ROOT / 'runtime/cache', args.offline, args.seed_cache)
    commands = []
    report = {'status': 'running', 'firmware_downloaded': False, 'apk_downloaded': False, 'commands': commands}
    def run(argv):
        p = subprocess.run([str(x) for x in argv], cwd=ROOT, capture_output=True, timeout=120)
        commands.append({'command': [str(x) for x in argv], 'exit_status': p.returncode,
            'stdout': p.stdout.decode('utf8', 'replace'), 'stderr': p.stderr.decode('utf8', 'replace')})
        if p.returncode:
            raise RuntimeError(commands[-1]['stderr'] or commands[-1]['stdout'])
        return p
    try:
        python_packages(lock, downloader)
        node = discover(cfg['node'])
        if not node:
            spec = lock['node']
            archive = downloader.obtain(spec['filename'], spec)
            extract_zip_files(archive, ROOT / 'runtime/node')
            node = str(next((ROOT / 'runtime/node').glob('*/node.exe')))
        if 'node' not in raw or args.node:
            raw['node'] = node
        clang = discover(cfg['clang'], ['C:/Program Files/LLVM/bin/clang.exe'])
        linker = discover(cfg['linker'], ['C:/Program Files/LLVM/bin/ld.lld.exe'])
        qemu = discover(cfg['qemu'], ['qemu-system-aarch64.exe'])
        if not qemu or not clang or not linker:
            from prepare_qemu import prepare
            tree = prepare(ROOT, llvm=not clang or not linker, qemu=not qemu, downloader=downloader)
            qemu = qemu or str(tree / 'bin/qemu-system-aarch64.exe')
            clang = clang or str(tree / 'bin/clang.exe')
            linker = linker or str(tree / 'bin/ld.lld.exe')
        for key, value in [('qemu', qemu), ('clang', clang), ('linker', linker)]:
            if key not in raw or getattr(args, key, None):
                raw[key] = value
        # Resolve explicit relative input locations against the repository, not scripts/.
        for key, default in DEFAULTS.items():
            raw.setdefault(key, default)
        config_file.write_text(json.dumps(raw, indent=2) + '\n', encoding='utf8')
        cfg = load(config_file)
        initramfs = Path(cfg['initramfs'])
        if not initramfs.exists():
            spec = native['alpine']['assets']['initramfs-virt']
            archive = downloader.obtain('initramfs-virt', spec)
            initramfs.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(archive, initramfs)
        else:
            print('Reused existing Alpine bootstrap:', initramfs)
        from prepare import prepare
        prepare(offline=args.offline)
        if args.reuse_renderers:
            pins = json.loads((ROOT / 'scripts/dependencies/renderer.lock.json').read_text())['files']
            (ROOT / 'build').mkdir(exist_ok=True)
            for name, pin in pins.items():
                source = (args.reuse_renderers / name).resolve()
                target = ROOT / 'build' / name
                if sha256(source) != pin['sha256']:
                    raise ValueError('Existing renderer differs from pin: ' + name)
                if not target.exists():
                    try:
                        os.link(source, target)
                    except OSError:
                        shutil.copyfile(source, target)
                if sha256(target) != pin['sha256']:
                    raise ValueError('Renderer destination differs: ' + name)
                print('Reused verified renderer:', name)
        from prepare_display import main as renderer
        firmware_ready = renderer(offline=args.offline)
        run([cfg['qemu'], '--version'])
        run([cfg['node'], '--version'])
        run([cfg['clang'], '--version'])
        run([cfg['linker'], '--version'])
        if firmware_ready:
            run([sys.executable, ROOT / 'build_display.py'])
        report.update(status='complete', firmware_link_inputs_present=firmware_ready,
            configured_paths=cfg, no_system_installation=True)
        (ROOT / 'runtime/python-command.json').write_text(json.dumps({'python': sys.executable}) + '\n')
        print('Public dependencies ready. Firmware/APK are private external inputs; no firmware was downloaded.')
    finally:
        report['downloads'] = downloader.records
        (ROOT / 'reports').mkdir(exist_ok=True)
        (ROOT / 'reports/dependency-setup.local.json').write_text(json.dumps(report, indent=2) + '\n')
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan', action='store_true')
    p.add_argument('--offline', action='store_true')
    p.add_argument('--seed-cache', type=Path)
    p.add_argument('--reuse-renderers', type=Path, help='Reuse hash-verified renderer files without downloading them')
    for key in ('qemu', 'initramfs', 'kernel', 'node', 'clang', 'linker', 'firmware_dir'):
        p.add_argument('--' + key.replace('_', '-'))
    try:
        return setup(p.parse_args())
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print('Setup stopped:', error, file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
