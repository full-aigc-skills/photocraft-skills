"""维护版逐命令确认合同；须显式提供候选二进制，不替代发行验收。"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

BINARY = os.environ.get('CRAFT_SUPERVISED_BINARY')

@unittest.skipUnless(BINARY, 'explicit maintained runtime candidate required')
class SupervisedRun(unittest.TestCase):
    def run_native(self, root, confirmations, *extra):
        target = root / 'project.pcraft'
        argv = [BINARY, 'run', '--supervised', '--new', '{"width":32,"height":32}',
                '--cmd', 'layer.new.layer', '--params', '{"name":"First"}', *extra, '--out', str(target)]
        result = subprocess.run(argv, input=confirmations, capture_output=True, text=True, timeout=30)
        events = [json.loads(line) for line in result.stdout.splitlines()]
        return result, events, target

    def test_eof_after_creation_stops_before_edit_and_save(self):
        with tempfile.TemporaryDirectory() as temporary:
            result, events, target = self.run_native(Path(temporary), '')
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual([event['tool'] for event in events], ['doc_new'])
            self.assertFalse(target.exists())

    def test_rejected_or_wrong_confirmation_stops_after_current_command(self):
        for reply in ['stop 2\n', 'continue 1\n', 'continue 2 extra\n', 'continue 2', 'x' * 4100 + '\n']:
            with self.subTest(reply=reply[:40]), tempfile.TemporaryDirectory() as temporary:
                result, events, target = self.run_native(Path(temporary), 'continue 1\n' + reply)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual([event['tool'] for event in events], ['doc_new', 'command_run'])
                self.assertEqual(events[-1]['arguments'], {'id':'layer.new.layer', 'params':{'name':'First'}})
                self.assertFalse(target.exists())

    def test_confirmed_run_saves_and_preserves_legacy_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result, events, target = self.run_native(root, 'continue 1\ncontinue 2\ncontinue 3\n')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual([event['sequence'] for event in events], [1, 2, 3])
            self.assertEqual([event['tool'] for event in events], ['doc_new', 'command_run', 'doc_save'])
            self.assertTrue(all(event['schema'] == 'photocraft-supervised-run/v1' for event in events))
            self.assertEqual([event['visible'] for event in events], [False, True, False])
            self.assertTrue(target.is_file())
            info = subprocess.run([BINARY, 'info', str(target)], capture_output=True, text=True, timeout=30)
            self.assertEqual(info.returncode, 0, info.stderr)
            self.assertTrue(any(layer['name'] == 'First' for layer in json.loads(info.stdout)['layers']))
            legacy = root / 'legacy.pcraft'
            old = subprocess.run([BINARY, 'run', '--new', '{"width":32,"height":32}', '--cmd', 'layer.new.layer',
                                  '--params', '{"name":"First"}', '--out', str(legacy)], capture_output=True, text=True, timeout=30)
            self.assertEqual(old.returncode, 0, old.stderr)
            self.assertEqual(json.loads(old.stdout)['command'], 'layer.new.layer')
            self.assertNotIn('schema', json.loads(old.stdout))

    def test_unacknowledged_save_preserves_actual_file_without_replay(self):
        with tempfile.TemporaryDirectory() as temporary:
            result, events, target = self.run_native(Path(temporary), 'continue 1\ncontinue 2\n')
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(events[-1]['tool'], 'doc_save')
            self.assertTrue(target.is_file())
            before = hashlib.sha256(target.read_bytes()).hexdigest()
            info = subprocess.run([BINARY, 'info', str(target)], capture_output=True, text=True, timeout=30)
            self.assertEqual(info.returncode, 0, info.stderr)
            self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), before)

    def test_native_failure_has_request_identity_and_stops(self):
        with tempfile.TemporaryDirectory() as temporary:
            # 未知命令由真实引擎拒绝；用于确认失败事件身份，而不是静态入口校验。
            result, events, target = self.run_native(Path(temporary), 'continue 1\ncontinue 2\n', '--cmd', 'not.a.command')
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(len(events), 3)
            self.assertEqual(events[-1]['arguments']['id'], 'not.a.command')
            self.assertIn('error', events[-1])
            self.assertNotIn('result', events[-1])
            self.assertFalse(target.exists())

if __name__ == '__main__':
    unittest.main()
