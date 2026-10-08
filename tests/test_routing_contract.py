"""显式意图路由查询不创建工程、不重复前置，也不重放未知编辑。"""
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/photocraft-use/scripts/route.py'


class RoutingContractTests(unittest.TestCase):
    def route(self, intent, *extra):
        result = subprocess.run([sys.executable, '-I', '-B', str(SCRIPT), intent, *extra], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_clear_intents_have_one_default_owner(self):
        for intent, owner in [('edit_text', 'photocraft-cli-text'), ('filter_background', 'photocraft-cli-filters'),
                              ('export', 'photocraft-cli-export'), ('query_commands', 'photocraft-cli')]:
            with self.subTest(intent=intent):
                self.assertEqual(self.route(intent)['skills'], [owner])

    def test_unknown_execution_goes_to_recovery_without_new_edits(self):
        result = self.route('edit_text', '--outcome', 'unknown')
        self.assertEqual(result['action'], 'reconcile')
        self.assertEqual(result['skills'], [])
        self.assertFalse(result['replayAllowed'])

    def test_reuses_completed_steps_and_respects_explicit_skill(self):
        result = self.route('poster', '--completed', 'photocraft-cli-project', '--completed', 'photocraft-cli-layers')
        self.assertEqual(result['skills'], ['photocraft-cli-text', 'photocraft-cli-export'])
        self.assertEqual(self.route('poster', '--skill', 'photocraft-cli')['skills'], ['photocraft-cli'])


if __name__ == '__main__':
    unittest.main()
