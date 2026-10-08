"""恢复决策读取结构化 outcome，而不是本地化错误文本。"""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1] / 'skills/photocraft-use/scripts'


class OperationErrorsTests(unittest.TestCase):
    def test_malformed_and_semantic_replies_expose_recovery_fields(self):
        spec = importlib.util.spec_from_file_location('typed_commands', ROOT / 'commands.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        for text, outcome, action in [('{"x":NaN}', 'unknown', 'reconcile'), ('{"error":"图层不存在"}', 'failed', 'inspect')]:
            with self.subTest(text=text):
                try:
                    module.parse_reply({'content': [{'type': 'text', 'text': text}]})
                except RuntimeError as error:
                    self.assertEqual(getattr(error, 'outcome', None), outcome)
                    self.assertEqual(getattr(error, 'phase', None), 'submitted')
                    self.assertEqual(getattr(error, 'recoveryAction', None), action)
                    self.assertIs(getattr(error, 'retryable', None), False)
                else:
                    self.fail('unsafe reply accepted')


if __name__ == '__main__':
    unittest.main()
