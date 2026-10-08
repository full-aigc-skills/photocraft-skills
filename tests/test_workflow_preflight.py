"""普通工作流必须在安装前拒绝歧义计划，并与网关共用回复语义。"""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/photocraft-use/scripts/workflow.py'


def workflow():
    spec = importlib.util.spec_from_file_location('strict_workflow', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WorkflowPreflightTests(unittest.TestCase):
    def test_invalid_plans_never_reach_runtime_preparation(self):
        base = {'document': {'width': 32, 'height': 32}, 'operations': []}
        cases = [
            {**base, 'operations': [{'command': 'type.setStyle', 'params': {'size': float('nan')}}]},
            {**base, 'operations': [{'command': 'type.setStyle', 'params': {'size': float('inf')}}]},
            {**base, 'operations': [{'command': 'layer.select', 'params': {'layer': {'$ref': 'missing.layer'}}}]},
            {**base, 'operations': [{'command': 'layer.new.layer', 'params': {}, 'typo': True}]},
            {**base, 'operations': [None]},
            {**base, 'assets': {'product': {'path': 'missing.png'}}},
            {**base, 'minimumLayers': True},
            {**base, 'typo': True},
        ]
        for plan in cases:
            with self.subTest(plan=plan), tempfile.TemporaryDirectory() as temporary:
                module = workflow()
                original = module.load_module
                def load(name):
                    if name == 'bootstrap':
                        self.fail('invalid plan reached runtime preparation')
                    return original(name)
                module.load_module = load
                output = Path(temporary) / 'output'
                with self.assertRaises(ValueError):
                    module.execute(plan, output, Path(temporary) / 'runtime')
                self.assertEqual(list(Path(temporary).iterdir()), [])

    def test_public_entry_rejects_duplicate_keys_before_writes(self):
        texts = [
            '{"document":{"width":16,"width":32,"height":32},"operations":[]}',
            '{"document":{"width":32,"height":32},"operations":[{"command":"type.setStyle","params":{"size":1e999}}]}',
        ]
        for text in texts:
            with self.subTest(text=text), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                plan = root / 'plan.json'
                plan.write_text(text)
                result = subprocess.run([sys.executable, '-I', '-B', str(SCRIPT), str(plan),
                    '--output', str(root / 'output'), '--runtime-home', str(root / 'runtime')], capture_output=True, text=True)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn(json.loads(result.stdout)['error'].split(':')[0],
                              ['duplicate_json_key', 'nonfinite_json_value', 'invalid_json_parameters'])
                self.assertEqual(sorted(p.name for p in root.iterdir()), ['plan.json'])

    def test_inherited_alias_is_checked_before_bootstrap(self):
        module = workflow()
        plan = {'operations': [{'command': 'layer.select', 'params': {'layer': {'$ref': 'title.layer'}}}]}
        module.validate(plan, {'title': {'layer': 42}})
        with self.assertRaisesRegex(ValueError, 'forward_or_unknown_reference'):
            module.validate(plan, {})

    def test_reply_semantics_do_not_publish_unverified_success(self):
        module = workflow()
        bad = [
            '{"layer":1,"layer":2}', '{"layer":NaN}', '{"layer":1e999}',
            '{"error":"invalid layer"}',
        ]
        for text in bad:
            with self.subTest(text=text):
                state, receipts = {}, []
                class Session:
                    def request(self, method, arguments):
                        return {'content': [{'type': 'text', 'text': text}]}
                with self.assertRaises(RuntimeError):
                    module.call_tool(Session(), 'command_run', {'id': 'layer.select', 'params': {}}, state, receipts)
                self.assertEqual(receipts, [])
                self.assertEqual(state['lastAttempt']['phase'], 'submitted')

    def test_valid_reply_records_only_validated_phase(self):
        module = workflow()
        state, receipts = {}, []
        class Session:
            def request(self, method, arguments):
                return {'content': [{'type': 'text', 'text': '{"layer":42}'}]}
        self.assertEqual(module.call_tool(Session(), 'command_run', {'id':'layer.new','params':{}}, state, receipts), {'layer': 42})
        self.assertEqual(state['lastAttempt']['phase'], 'reply_validated')
        self.assertEqual(len(receipts), 1)


if __name__ == '__main__':
    unittest.main()

class CheckOnlyTests(unittest.TestCase):
 def test_check_does_not_install_or_create_output(self):
  import subprocess
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);plan=root/'plan.json';plan.write_text('{"document":{"width":32,"height":32},"operations":[]}')
   result=subprocess.run([sys.executable,str(SCRIPT),str(plan),'--check','--runtime-home',str(root/'runtime')],capture_output=True,text=True)
   self.assertEqual(result.returncode,0,result.stdout+result.stderr)
   self.assertEqual(json.loads(result.stdout)['result'],'PASS');self.assertFalse((root/'runtime').exists())
