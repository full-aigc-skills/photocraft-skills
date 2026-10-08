"""监督器候选：同会话合法调用、真实回复后的停止及保存保全。"""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / 'skills/photocraft-use/scripts'
spec = importlib.util.spec_from_file_location('candidate_supervisor', SCRIPTS/'cli_supervisor.py')
supervisor = importlib.util.module_from_spec(spec); spec.loader.exec_module(supervisor)
BINARY = os.environ.get('CRAFT_SUPERVISED_BINARY')

class SupervisionPlanning(unittest.TestCase):
    def test_original_flag_order_last_parameters_and_format_are_bound(self):
        events = supervisor.expected_events(['run', '--new={"width":32}', '--cmd=layer.new.layer', '--params={"name":"old"}',
                                             '--params={"name":"last"}', '--out=out.pcraft', '--format=pcraft', '--quality=+010'])
        self.assertEqual(events, [('doc_new', {'width':32}, False), ('command_run', {'id':'layer.new.layer','params':{'name':'last'}}, True),
                                  ('doc_save', {'path':'out.pcraft','format':'pcraft','quality':10}, False)])

    def test_invalid_input_never_starts_process_or_emits_output(self):
        output = io.StringIO()
        with mock.patch.object(supervisor.subprocess, 'Popen') as launch:
            with self.assertRaises(ValueError):
                supervisor.execute('unused', ['run','--new={"width":NaN}','--out=x.pcraft'], output)
            launch.assert_not_called()
        self.assertEqual(output.getvalue(), '')

@unittest.skipUnless(BINARY, 'explicit maintained runtime candidate required')
class NativeSupervision(unittest.TestCase):
    def test_healthy_create_aside_revision_preserves_source_and_public_lines(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); original = root/'original.pcraft'; revised = root/'revised.pcraft'; output = io.StringIO()
            result = supervisor.execute(BINARY, ['run','--new={"width":32,"height":32}','--cmd=layer.new.layer','--params={"name":"Original"}','--out',str(original)], output)
            self.assertEqual(result['result'], 'PASS'); self.assertEqual(len(result['receipts']), 3)
            receipt = json.loads(output.getvalue()); self.assertEqual(receipt['command'], 'layer.new.layer')
            before = hashlib.sha256(original.read_bytes()).hexdigest(); output = io.StringIO()
            result = supervisor.execute(BINARY, ['run',str(original),'--cmd=layer.new.layer','--params={"name":"Revision"}','--out',str(revised)], output)
            self.assertEqual(result['result'], 'PASS'); self.assertTrue(revised.is_file())
            self.assertEqual(hashlib.sha256(original.read_bytes()).hexdigest(), before)
            self.assertEqual(len(output.getvalue().splitlines()), 1)

    def test_actual_native_reply_fault_stops_before_next_command_and_save(self):
        for fault in ['duplicate','nonfinite','semantic','wrong-request','extra-frame']:
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary); log = root/'events.jsonl'; target = root/'never.pcraft'; output = io.StringIO()
                with mock.patch.dict(os.environ, CRAFT_SUPERVISED_LOG=str(log), CRAFT_SUPERVISED_FAULT=fault, CRAFT_SUPERVISED_AT='2'):
                    with self.assertRaises(Exception) as caught:
                        supervisor.execute(ROOT/'runtime/tests/fixtures/supervised_proxy.py',
                            ['run','--new={"width":32,"height":32}','--cmd=layer.new.layer','--params={"name":"First"}',
                             '--cmd=layer.new.layer','--params={"name":"Never"}','--out',str(target)], output)
                error = caught.exception
                self.assertEqual(error.outcome, 'failed' if fault == 'semantic' else 'unknown')
                self.assertFalse(error.retryable)
                self.assertEqual(len(error.receipts), 1)
                self.assertEqual(error.lastAttempt['sequence'], 2)
                self.assertEqual(output.getvalue(), '')
                rows = [json.loads(line) for line in log.read_text().splitlines()]
                self.assertEqual([r['nativeEvent']['sequence'] for r in rows if 'nativeEvent' in r], [1,2])
                self.assertEqual([r['confirmation'] for r in rows if 'confirmation' in r], ['continue 1\n'])
                self.assertFalse(target.exists())

    def test_malformed_actual_save_retains_file_and_previous_receipts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); target = root/'saved.pcraft'; log = root/'events.jsonl'
            with mock.patch.dict(os.environ, CRAFT_SUPERVISED_LOG=str(log), CRAFT_SUPERVISED_FAULT='save-array', CRAFT_SUPERVISED_AT='3'):
                with self.assertRaises(Exception) as caught:
                    supervisor.execute(ROOT/'runtime/tests/fixtures/supervised_proxy.py',
                        ['run','--new={"width":32,"height":32}','--cmd=layer.new.layer','--params={"name":"Saved"}','--out',str(target)], io.StringIO())
            self.assertEqual(caught.exception.outcome, 'unknown')
            self.assertEqual(len(caught.exception.receipts), 2)
            self.assertTrue(target.is_file())
            before = hashlib.sha256(target.read_bytes()).hexdigest()
            # 原路径只读重开；无需重放先前编辑或复制重建工程。
            import subprocess
            info = subprocess.run([BINARY, 'info', str(target)], capture_output=True, text=True, timeout=30)
            self.assertEqual(info.returncode, 0, info.stderr)
            self.assertTrue(any(row['name']=='Saved' for row in json.loads(info.stdout)['layers']))
            self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), before)
            rows = [json.loads(line) for line in log.read_text().splitlines()]
            self.assertEqual([r['confirmation'] for r in rows if 'confirmation' in r], ['continue 1\n', 'continue 2\n'])

if __name__ == '__main__':
    unittest.main()
