"""发行检查必须发现套件与技能包身份漂移，允许独立运行时版本。"""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ReleaseIdentityTests(unittest.TestCase):
    def test_current_combination_is_checkable(self):
        result = subprocess.run([sys.executable, '-I', '-B', str(ROOT / 'scripts/check_release_identity.py')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['runtimeVariant'], 'maintained-capability-scoped-smart-content')

    def test_mismatched_suite_is_rejected_without_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ['.claude-plugin/plugin.json', 'skill-suite.json', 'skills/photocraft-use/scripts/runtime.lock.json']:
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, target)
            suite = root / 'skill-suite.json'
            data = json.loads(suite.read_text()); data['version'] = '0.1.0-dev.1'
            suite.write_text(json.dumps(data)); before = suite.read_bytes()
            result = subprocess.run([sys.executable, '-I', '-B', str(ROOT / 'scripts/check_release_identity.py'), '--root', str(root)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn('suite_version_mismatch', json.loads(result.stdout)['errors'])
            self.assertEqual(suite.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
