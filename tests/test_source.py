from pathlib import Path
import gzip
import hashlib
import importlib.util
import io
import json
import os
import socket
import struct
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
import config
import run as bench
import sparse_nbd
import audit_public
from dependency_utils import Downloader, destination, extract_tar_files


def fake_alpine():
    data = bench.entry('usr/bin/busybox', b'\x7fELFtest-busybox', 0o100755)
    data += bench.entry('usr/lib/ld-musl-aarch64.so.1', b'\x7fELFtest-loader', 0o100755)
    data += bench.entry('TRAILER!!!')
    return gzip.compress(data)


def sparse_fixture(path):
    raw = b'ABCD' * 1024
    header = struct.pack('<I4H4I', 0xed26ff3a, 1, 0, 28, 12, 4096, 3, 3, 0)
    chunks = struct.pack('<2H2I', 0xcac1, 0, 1, 12 + 4096) + raw
    chunks += struct.pack('<2H2I', 0xcac2, 0, 1, 16) + b'WXYZ'
    chunks += struct.pack('<2H2I', 0xcac3, 0, 1, 12)
    path.write_bytes(header + chunks)


class ConfigTests(unittest.TestCase):
    def test_example_has_no_machine_specific_paths(self):
        raw = json.loads((ROOT / 'config.example.json').read_text())
        self.assertEqual(set(raw), set(config.DEFAULTS))
        self.assertEqual(raw['firmware_dir'], 'local/firmware')

    def test_relative_paths_resolve_at_config_file(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'config.local.json'
            p.write_text(json.dumps({'firmware_dir': 'inputs'}))
            self.assertEqual(config.load(p)['firmware_dir'], str((p.parent / 'inputs').resolve()))

    def test_unknown_configuration_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'config.local.json'
            p.write_text('{"unexpected": "x"}')
            with self.assertRaises(ValueError):
                config.load(p)

    def test_existing_configuration_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'config.local.json'
            p.write_text('original')
            self.assertFalse(config.save_new(p, {'node': 'changed'}))
            self.assertEqual(p.read_text(), 'original')


class ArchiveTests(unittest.TestCase):
    def test_cpio_alignment_and_payload(self):
        b = bench.entry('hello', b'abc', 0o100755, 17)
        self.assertEqual(len(b) % 4, 0)
        self.assertEqual(int(b[54:62], 16), 3)
        self.assertIn(b'hello\0', b)

    def test_ramdisk_uses_synthetic_fixture_not_firmware(self):
        with tempfile.TemporaryDirectory() as td:
            init = Path(td) / 'initramfs'
            init.write_bytes(fake_alpine())
            with patch.object(bench, 'CONFIG', {'initramfs': str(init)}):
                target = Path(td) / 'out.gz'
                rows = bench.build_initramfs(target, 'headless')
            self.assertIn('init', [r['path'] for r in rows])
            self.assertIn(b'ANDROID_BENCH_BEGIN', gzip.decompress(target.read_bytes()))

    def test_archive_path_traversal_rejected(self):
        for member in ['../outside', '/absolute', 'x/../../y', 'C:/outside', 'a\\b']:
            with self.assertRaises(ValueError):
                destination(ROOT, member)

    def test_regular_files_only_extracted(self):
        with tempfile.TemporaryDirectory() as td:
            b = io.BytesIO()
            with tarfile.open(fileobj=b, mode='w') as t:
                member = tarfile.TarInfo('valid.txt')
                member.size = 2
                t.addfile(member, io.BytesIO(b'ok'))
                link = tarfile.TarInfo('link')
                link.type = tarfile.SYMTYPE
                link.linkname = '../outside'
                t.addfile(link)
            b.seek(0)
            with tarfile.open(fileobj=b) as t:
                extract_tar_files(t, Path(td))
            self.assertEqual((Path(td) / 'valid.txt').read_bytes(), b'ok')
            self.assertFalse((Path(td) / 'link').exists())


class SparseTests(unittest.TestCase):
    def test_sparse_raw_fill_and_zero(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'fixture.img'
            sparse_fixture(p)
            image = sparse_nbd.SparseImage(p)
            try:
                self.assertEqual(image.size, 12288)
                self.assertEqual(image.read(4094, 6), b'CDWXYZ')
                self.assertEqual(image.read(8192, 16), bytes(16))
                with self.assertRaises(ValueError):
                    image.read(12288, 1)
            finally:
                image.close()

    def test_sparse_original_opened_readonly(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'fixture.img'
            sparse_fixture(p)
            before = p.read_bytes()
            image = sparse_nbd.SparseImage(p)
            self.assertEqual(image.file.mode, 'rb')
            image.close()
            self.assertEqual(p.read_bytes(), before)


class DependencyTests(unittest.TestCase):
    def test_verified_cache_works_offline(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'public.txt'
            p.write_bytes(b'public fixture')
            spec = {'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'size': p.stat().st_size}
            self.assertEqual(Downloader(td, offline=True).obtain(p.name, spec), p.resolve())

    def test_changed_cache_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / 'public.txt').write_bytes(b'wrong')
            with self.assertRaises(ValueError):
                Downloader(td, offline=True).obtain('public.txt', {'sha256': '0' * 64})

    def test_locks_have_no_firmware_or_apk_source(self):
        boot = json.loads((ROOT / 'scripts/dependencies/bootstrap.lock.json').read_text())
        self.assertIn('www.python.org', boot['python']['url'])
        self.assertIn('nodejs.org', boot['node']['url'])
        for row in boot['python_packages'].values():
            self.assertTrue(row['wheels'])
            for wheel in row['wheels']:
                self.assertEqual(len(wheel['sha256']), 64)
                self.assertIn('files.pythonhosted.org', wheel['url'])

    def test_setup_plan_never_accesses_private_inputs(self):
        p = subprocess.run([sys.executable, str(ROOT / 'scripts/setup_dependencies.py'), '--plan'], capture_output=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        plan = json.loads(p.stdout)
        self.assertFalse(plan['firmware_downloaded'])
        self.assertFalse(plan['apk_downloaded'])
        self.assertTrue(plan['reuse_existing_first'])


class PublicBoundaryTests(unittest.TestCase):
    def test_public_source_audit(self):
        result = audit_public.audit()
        self.assertTrue(result['passed'], result['errors'])

    def test_binary_magic_rejected(self):
        self.assertTrue(audit_public.check_bytes('unexpected.txt', b'\x7fELF' + bytes(32)))

    def test_private_directory_rejected_even_for_text(self):
        self.assertTrue(audit_public.check_bytes('original/init.rc', b'plain text'))
        self.assertTrue(audit_public.check_bytes('data/user.txt', b'plain text'))

    def test_manifest_cannot_opt_in_firmware_extension(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'manifest.json'
            p.write_text('{"files": ["system.img"]}')
            with patch.object(audit_public, 'MANIFEST', p), self.assertRaises(ValueError):
                audit_public.public_files()

    def test_actual_forced_git_index_artifact_is_detected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'safe.py').write_text('print(1)\n')
            (root / 'private.img').write_bytes(b'\x7fELFsynthetic')
            manifest = root / 'manifest.json'
            manifest.write_text('{"files": ["safe.py"]}')
            for args in [['git', 'init', '-q'], ['git', 'add', 'safe.py'], ['git', 'add', '-f', 'private.img']]:
                subprocess.run(args, cwd=root, check=True, capture_output=True)
            with patch.object(audit_public, 'ROOT', root), patch.object(audit_public, 'MANIFEST', manifest):
                result = audit_public.audit(require_index=True)
            self.assertFalse(result['passed'])
            self.assertTrue(any('private.img' in e for e in result['errors']))

    def test_staged_secret_is_checked_even_if_worktree_clean(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            key = b'-----BEGIN ' + b'PRIVATE KEY-----'
            (root / 'safe.py').write_bytes(key)
            manifest = root / 'manifest.json'
            manifest.write_text('{"files": ["safe.py"]}')
            subprocess.run(['git', 'init', '-q'], cwd=root, check=True, capture_output=True)
            subprocess.run(['git', 'add', 'safe.py'], cwd=root, check=True, capture_output=True)
            (root / 'safe.py').write_text('clean worktree\n')
            with patch.object(audit_public, 'ROOT', root), patch.object(audit_public, 'MANIFEST', manifest):
                result = audit_public.audit(require_index=True)
            self.assertFalse(result['passed'])
            self.assertTrue(any('private-key' in e for e in result['errors']))

    def test_secret_rejected(self):
        value = b'-----BEGIN ' + b'PRIVATE KEY-----'
        self.assertTrue(audit_public.check_bytes('secret.txt', value))

    def test_private_path_rejected(self):
        value = b'C:' + b'\\Users\\' + b'Example\\input.img'
        self.assertTrue(audit_public.check_bytes('private.txt', value))

    def test_no_sibling_project_imports(self):
        source = (ROOT / 'run.py').read_text()
        self.assertNotIn('mib3-hmi-bench/src', source)
        self.assertNotIn('agl-arm64-runtime', source)

    def test_documents_name_original_firmware_components(self):
        s = (ROOT / 'docs/BOUNDARIES.md').read_text(encoding='utf8')
        for term in ['SurfaceFlinger', 'ART', 'system_server', 'SwiftShader', 'MIT']:
            self.assertIn(term, s)

    def test_diagnostics_remain_loopback(self):
        self.assertIn('127.0.0.1', (ROOT / 'run.py').read_text())
        self.assertNotIn('0.0.0.0', (ROOT / 'display_viewer.py').read_text(encoding='utf8'))

    def test_hal_uses_real_buffers_not_app_assets(self):
        source = (ROOT / 'native/gralloc-bench.c').read_text()
        self.assertIn('ashmem_create_region', source)
        self.assertIn('sendall(transport,pixels,header[5])', source)
        self.assertNotIn('base.apk', source)


if __name__ == '__main__':
    unittest.main()
