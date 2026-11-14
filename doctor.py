"""Validate local prerequisites without booting, modifying or distributing firmware."""
from pathlib import Path
import argparse
import shutil
from config import ROOT, load


def check(cfg, mode='graphics'):
    missing = []
    for name in ('qemu', 'kernel', 'initramfs'):
        if not Path(cfg[name]).is_file():
            missing.append(name)
    for name in ('system.img', 'vendor.img', 'userdata.img'):
        if not (Path(cfg['firmware_dir']) / name).is_file():
            missing.append('user-supplied ' + name)
    if mode == 'graphics':
        for name in ('gralloc.bench.so', 'seed-rng', 'egl-probe', 'libEGL_swiftshader.so', 'libGLESv1_CM_swiftshader.so', 'libGLESv2_swiftshader.so'):
            if not (ROOT / 'build' / name).is_file():
                missing.append('build/' + name)
        try:
            import sys
            packages = ROOT / 'runtime/python-packages'
            if packages.is_dir():
                sys.path.insert(0, str(packages))
            from PIL import Image
        except ImportError:
            missing.append('Pillow')
    if missing:
        raise FileNotFoundError('Missing prerequisites: ' + ', '.join(missing) + '. Run setup and supply the documented local inputs.')
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, default=ROOT / 'config.local.json')
    parser.add_argument('--mode', choices=['probe', 'headless', 'graphics'], default='graphics')
    args = parser.parse_args()
    check(load(args.config), args.mode)
    print('PASS prerequisites; no firmware process started')
