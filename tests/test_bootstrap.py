"""首次安装的可观察行为；所有测试均使用隔离目录。"""
import hashlib
import importlib.util
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import zipfile

SOURCE = Path(__file__).resolve().parents[1] / 'skills/photocraft-use/scripts/bootstrap.py'


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('bootstrap', SOURCE)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.binary = b'#!/bin/sh\nprintf "filmcraft-cli 0.2.0\\n"\n'
        self.archive = self.root / 'official.zip'
        self.make_archive()

    def make_archive(self, extra=None):
        with zipfile.ZipFile(self.archive, 'w') as z:
            z.writestr('filmcraft-cli', self.binary)
            z.writestr('LICENSE-MIT', 'Fixture license')
            if extra:
                z.writestr(*extra)
        self.lock = {'artifact': 'filmcraft-cli', 'resolvedVersion': '0.2.0',
                     'artifacts': {'darwin-arm64': {
                         'url': 'https://github.com/storytold/filmcraft/releases/download/v0.2.0/fixture.zip',
                         'archiveSha256': hashlib.sha256(self.archive.read_bytes()).hexdigest(),
                         'binarySha256': hashlib.sha256(self.binary).hexdigest()}}}

    def install(self):
        return self.module.install(self.lock, self.root / 'runtime', self.archive, 'darwin-arm64')

    def test_clean_install_and_reuse_without_network(self):
        first = self.install()
        self.archive.unlink()
        with patch.object(self.module, 'download', side_effect=AssertionError('network on reuse')):
            second = self.install()
        self.assertEqual(first['executable'], second['executable'])
        self.assertTrue(second['reused'])
        self.assertEqual(Path(first['executable']).read_bytes(), self.binary)
        self.assertTrue((Path(first['executable']).parent / 'LICENSE-MIT').exists())
        self.assertEqual(json.loads((Path(first['executable']).parent / 'installation.json').read_text())['version'], '0.2.0')

    def test_corrupt_download_never_runs(self):
        self.archive.write_bytes(b'corrupt')
        with patch.object(self.module.subprocess, 'run', side_effect=AssertionError('executed')):
            with self.assertRaisesRegex(ValueError, 'archive_checksum'):
                self.install()
        self.assertFalse((self.root / 'runtime/filmcraft/0.2.0').exists())

    def test_traversal_rejected_before_extract(self):
        self.make_archive(('../escaped', 'unsafe'))
        with self.assertRaisesRegex(ValueError, 'unsafe_archive'):
            self.install()
        self.assertFalse((self.root / 'runtime/filmcraft/escaped').exists())

    def test_symlink_archive_rejected(self):
        link = zipfile.ZipInfo('link')
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        self.make_archive((link, '/tmp/elsewhere'))
        with self.assertRaisesRegex(ValueError, 'unsafe_archive'):
            self.install()

    def test_tampered_installed_binary_is_not_overwritten(self):
        first = self.install()
        path = Path(first['executable'])
        path.write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError, 'installed_checksum'):
            self.install()
        self.assertEqual(path.read_bytes(), b'tampered')

    def test_pinned_build_metadata_is_accepted(self):
        self.binary = b'#!/bin/sh\nprintf "filmcraft-cli 0.2.0 (build, date)\\n"\n'
        self.make_archive()
        self.lock['artifacts']['darwin-arm64']['versionOutput'] = 'filmcraft-cli 0.2.0 (build, date)'
        self.assertFalse(self.install()['reused'])

    def test_maintained_version_installs_without_replacing_official(self):
        official=self.install()
        self.binary=b'#!/bin/sh\nprintf "filmcraft-cli 0.2.0-craft.1\\n"\n'
        self.make_archive();self.lock['resolvedVersion']='0.2.0-craft.1'
        maintained=self.install()
        self.assertNotEqual(official['executable'],maintained['executable'])
        self.assertTrue(Path(official['executable']).is_file())

    def test_only_pinned_photo_release_urls_trusted(self):
        self.assertTrue(self.module.trusted_release_url('https://github.com/full-aigc-skills/photocraft-skills/releases/download/runtime-v0.2.0-craft.1/photo.zip'))
        self.assertTrue(self.module.trusted_release_url('https://github.com/storytold/photocraft/releases/download/v0.2.0/photo.zip'))
        for url in ['https://github.com/storytold/other/releases/download/v1/a.zip','https://github.com.evil/photocraft/a.zip','https://github.com/full-aigc-skills/photocraft-skills/releases/download/x/a.zip?token=x']:
            self.assertFalse(self.module.trusted_release_url(url))

    def test_unknown_platform_fails_without_download(self):
        with patch.object(self.module, 'download', side_effect=AssertionError('downloaded')):
            with self.assertRaisesRegex(ValueError, 'unsupported_platform'):
                self.module.install(self.lock, self.root / 'runtime', platform_key='unknown')

    def hold_install_lock(self):
        import subprocess
        import sys
        path = self.root / 'runtime/filmcraft/.install.lock'
        path.parent.mkdir(parents=True, exist_ok=True)
        child = subprocess.Popen([sys.executable, '-c', "import fcntl,sys; f=open(sys.argv[1],'w'); fcntl.flock(f,fcntl.LOCK_EX); print('locked',flush=True); sys.stdin.readline()", str(path)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        self.assertEqual(child.stdout.readline().strip(), 'locked')
        self.addCleanup(lambda: child.poll() is None and child.kill())
        return child

    def test_busy_installer_waits_for_other_process_and_reuses_verified_install(self):
        import threading
        self.install()
        child = self.hold_install_lock()
        release = threading.Timer(.15, lambda: child.stdin.write('release\n') and child.stdin.flush())
        release.start()
        try:
            result = self.install()
            self.assertTrue(result['reused'])
            self.assertEqual(Path(result['executable']).read_bytes(), self.binary)
        finally:
            release.join(); child.wait(timeout=5); child.stdin.close(); child.stdout.close()

    def test_busy_installer_timeout_preserves_existing_install(self):
        initial = self.install()
        child = self.hold_install_lock()
        try:
            with patch.object(self.module, 'LOCK_WAIT_SECONDS', .05, create=True):
                with self.assertRaisesRegex(TimeoutError, 'runtime_install_busy'):
                    self.install()
            self.assertEqual(Path(initial['executable']).read_bytes(), self.binary)
        finally:
            child.stdin.write('release\n'); child.stdin.flush(); child.wait(timeout=5); child.stdin.close(); child.stdout.close()

    def test_two_processes_first_install_once_and_share_verified_result(self):
        import subprocess
        import sys
        code = "import importlib.util,json,sys; spec=importlib.util.spec_from_file_location('boot',sys.argv[1]); boot=importlib.util.module_from_spec(spec); spec.loader.exec_module(boot); print(json.dumps(boot.install(json.loads(sys.argv[2]),sys.argv[3],sys.argv[4],'darwin-arm64')))"
        argv = [sys.executable, '-I', '-B', '-c', code, str(SOURCE), json.dumps(self.lock), str(self.root/'runtime'), str(self.archive)]
        children = [subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(2)]
        results = []
        for child in children:
            stdout, stderr = child.communicate(timeout=10)
            self.assertEqual(child.returncode, 0, stderr)
            results.append(json.loads(stdout))
        self.assertEqual(sorted(item['reused'] for item in results), [False, True])
        self.assertEqual(results[0]['executable'], results[1]['executable'])
        self.assertEqual(Path(results[0]['executable']).read_bytes(), self.binary)


if __name__ == '__main__':
    unittest.main()
