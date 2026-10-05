"""真实单技能隔离安装；必须显式启用，不把跳过当作通过。"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

@unittest.skipUnless(os.environ.get('CRAFT_LIVE_TEST') == '1', 'requires real official download')
class FirstUseTests(unittest.TestCase):
    def test_single_skill_without_plugin_or_siblings(self):
        package = Path(__file__).resolve().parents[1]
        name = package.name.removesuffix('-skills')
        with tempfile.TemporaryDirectory(prefix='craft-first-use-') as tmp:
            root = Path(tmp)
            skill = root / 'single-skill'
            shutil.copytree(package / 'skills' / (name + '-use'), skill, ignore=shutil.ignore_patterns('__pycache__'))
            def run(argv):
                result = subprocess.run(argv, cwd=root, capture_output=True, text=True, timeout=180)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                return result.stdout
            setup = [sys.executable, str(skill / 'scripts/bootstrap.py'), '--runtime-home', str(root / 'runtime')]
            first = json.loads(run(setup))
            self.assertFalse(first['reused'])
            cli = first['executable']
            args = {'effectcraft': ['info', '--json'], 'photocraft': ['commands', '--json'], 'vectorcraft': ['commands']}[name]
            data = json.loads(run([cli, *args]))
            self.assertTrue(data)
            second = json.loads(run(setup))
            self.assertTrue(second['reused'])
            self.assertEqual(first['executable'], second['executable'])

if __name__ == '__main__':
    unittest.main()
