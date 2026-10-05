"""计划边界和对象引用测试，不需要安装原生 CLI。"""
import importlib.util
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'skills/photocraft-use/scripts/workflow.py'

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('workflow', SOURCE)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def test_resolve_only_explicit_references(self):
        value = {'ids': [{'$ref': 'logo.id'}], 'text': 'logo.id'}
        self.assertEqual(self.module.resolve(value, {'logo': {'id': 12}}), {'ids': [12], 'text': 'logo.id'})

    def test_unknown_reference_is_an_error(self):
        with self.assertRaisesRegex(ValueError, 'unresolved_reference'):
            self.module.resolve({'$ref': 'missing.id'}, {})

    def test_file_side_effect_commands_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'unsupported_command'):
            self.module.validate({'operations': [{'command': 'document.save', 'params': {'path': '/outside'}}]})

    def test_duplicate_alias_rejected(self):
        with self.assertRaisesRegex(ValueError, 'duplicate_alias'):
            self.module.validate({'operations': [{'command': 'shape.create', 'as': 'logo'}, {'command': 'type.create', 'as': 'logo'}]})

    def test_export_range_and_format_rejected(self):
        for output in [{'format': 'exe', 'artboard': 0}, {'format': 'png', 'path': '/outside'}]:
            with self.assertRaises(ValueError):
                self.module.validate({'operations': [], 'exports': [output]})

if __name__ == '__main__':
    unittest.main()
