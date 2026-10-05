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

    def test_unknown_platform_fails_without_download(self):
        with patch.object(self.module, 'download', side_effect=AssertionError('downloaded')):
            with self.assertRaisesRegex(ValueError, 'unsupported_platform'):
                self.module.install(self.lock, self.root / 'runtime', platform_key='unknown')


if __name__ == '__main__':
    unittest.main()
