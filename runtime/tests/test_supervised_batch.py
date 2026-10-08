"""原生批处理监督：原文件保全、逐文件会话、错误停止及旧输出兼容。"""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
BINARY = os.environ.get('CRAFT_SUPERVISED_BINARY')
spec = importlib.util.spec_from_file_location('batch_supervisor_candidate', ROOT/'skills/photocraft-use/scripts/cli_supervisor.py')
supervisor = importlib.util.module_from_spec(spec); spec.loader.exec_module(supervisor)

class BatchPlanning(unittest.TestCase):
    def test_fixed_codec_selection_and_plan_never_write_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);inputs=root/'inputs';inputs.mkdir();actions=root/'actions.json';actions.write_text('[]')
            for name in ['b.PNG','a.psb','c.TIF','ignored.avif','ignored.txt','.pcraft','d.x\\png']:
                (inputs/name).write_bytes(b'planning fixture, never opened')
            (inputs/'directory.png').mkdir();output=root/'output'
            events,checks,lines=supervisor.batch_plan(['batch','--actions',str(actions),'--in',str(inputs),'--out',str(output)])
            self.assertEqual([Path(row['input']).name for row in checks[1]['files']],['a.psb','b.PNG','c.TIF','d.x\\png'])
            self.assertEqual(len(events),10);self.assertEqual(checks[10],{'succeeded':4,'failed':0})
            self.assertEqual(lines[10],'4 succeeded, 0 failed\n');self.assertFalse(output.exists())

    def test_invalid_actions_never_scan_input_launch_or_emit_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);actions=root/'actions.json'
            actions.write_text('[{"id":"layer.new.layer","params":{"name":"A","name":"B"}}]')
            text=io.StringIO()
            with mock.patch.object(supervisor.os,'scandir') as scan,mock.patch.object(supervisor.subprocess,'Popen') as launch:
                with self.assertRaises(ValueError):
                    supervisor.execute('unused',['batch','--actions',str(actions),'--in',str(root),'--out',str(root/'out')],text)
                scan.assert_not_called();launch.assert_not_called()
            self.assertEqual(text.getvalue(),'');self.assertFalse((root/'out').exists())

@unittest.skipUnless(BINARY, 'explicit maintained runtime candidate required')
class SupervisedBatch(unittest.TestCase):
    def prepare(self, root, actions=None):
        inputs = root/'inputs'; inputs.mkdir()
        for name in ['b.pcraft','a.pcraft']:
            result = subprocess.run([BINARY,'run','--new={"width":32,"height":32}', '--out',str(inputs/name)],capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stderr)
        file = root/'actions.json'
        file.write_text(json.dumps({'actions':actions if actions is not None else [{'id':'layer.new.layer','params':{'name':'Batch'}}]}))
        output = root/'output'
        argv = ['batch','--actions',str(file),'--in',str(inputs),'--out',str(output)]
        return inputs,output,argv

    def native(self, argv, ack=''):
        return subprocess.run([BINARY,argv[0],'--supervised',*argv[1:]],input=ack,capture_output=True,text=True,timeout=30)

    def test_unconfirmed_plan_never_creates_output_or_starts_document(self):
        with tempfile.TemporaryDirectory() as temporary:
            _,output,argv = self.prepare(Path(temporary))
            result = self.native(argv)
            self.assertNotEqual(result.returncode,0)
            events = [json.loads(line) for line in result.stdout.splitlines()]
            self.assertEqual([e['tool'] for e in events],['batch_plan'])
            self.assertFalse(output.exists())

    def test_native_sorted_fresh_sessions_and_full_confirmation(self):
        with tempfile.TemporaryDirectory() as temporary:
            inputs,output,argv = self.prepare(Path(temporary))
            before = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs.iterdir()}
            result = self.native(argv,''.join('continue '+str(n)+'\n' for n in range(1,9)))
            self.assertEqual(result.returncode,0,result.stderr)
            events = [json.loads(line) for line in result.stdout.splitlines()]
            self.assertEqual([e['tool'] for e in events],['batch_plan','doc_open','command_run','doc_save','doc_open','command_run','doc_save','batch_complete'])
            self.assertEqual([Path(e['arguments']['path']).name for e in events if e['tool']=='doc_open'],['a.pcraft','b.pcraft'])
            self.assertEqual([e['result']['index'] for e in events if e['tool']=='doc_open'],[0,0])
            self.assertEqual(events[-1]['result'],{'succeeded':2,'failed':0})
            self.assertTrue(all(e['visible'] is False for e in events))
            self.assertEqual(sorted(p.name for p in output.iterdir()),['a.pcraft','b.pcraft'])
            self.assertEqual({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs.iterdir()},before)

    def test_eof_after_actual_first_save_stops_before_second_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            inputs,output,argv = self.prepare(Path(temporary))
            result = self.native(argv,'continue 1\ncontinue 2\ncontinue 3\n')
            self.assertNotEqual(result.returncode,0)
            events = [json.loads(line) for line in result.stdout.splitlines()]
            self.assertEqual([e['tool'] for e in events],['batch_plan','doc_open','command_run','doc_save'])
            self.assertTrue((output/'a.pcraft').is_file());self.assertFalse((output/'b.pcraft').exists())
            self.assertEqual(sorted(p.name for p in inputs.iterdir()),['a.pcraft','b.pcraft'])

    def test_known_native_failure_stops_supervision_but_legacy_keeps_continuation(self):
        with tempfile.TemporaryDirectory() as temporary:
            inputs,output,argv = self.prepare(Path(temporary));(inputs/'a.pcraft').write_bytes(b'invalid native document')
            result = self.native(argv,'continue 1\n')
            self.assertNotEqual(result.returncode,0)
            events = [json.loads(line) for line in result.stdout.splitlines()]
            self.assertEqual([e['tool'] for e in events],['batch_plan','doc_open'])
            self.assertIn('error',events[-1]);self.assertFalse((output/'b.pcraft').exists())
            legacy = subprocess.run([BINARY,*argv],capture_output=True,text=True,timeout=30)
            self.assertEqual(legacy.returncode,1)
            self.assertIn('1 succeeded, 1 failed',legacy.stdout)
            self.assertTrue((output/'b.pcraft').is_file())

    def test_healthy_supervisor_keeps_original_stdout_and_format_quality(self):
        with tempfile.TemporaryDirectory() as temporary:
            _,output,argv = self.prepare(Path(temporary));argv.extend(['--format=jpg','--quality=+010'])
            legacy = subprocess.run([BINARY,*argv],capture_output=True,text=True,timeout=30)
            self.assertEqual(legacy.returncode,0,legacy.stderr)
            actual = io.StringIO();result = supervisor.execute(BINARY,argv,actual)
            self.assertEqual(result['result'],'PASS');self.assertEqual(actual.getvalue(),legacy.stdout)
            self.assertEqual(sorted(p.name for p in output.iterdir()),['a.jpg','b.jpg'])
            self.assertEqual([r['arguments']['quality'] for r in result['receipts'] if r['tool']=='doc_save'],[10,10])

    def test_empty_inputs_and_legacy_relative_path_spelling_remain_valid(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);inputs,output,argv=self.prepare(root)
            # 原生路径包含重复分隔符、父目录和点组件；不按自动化目录规则收窄 raw 合同。
            argv[argv.index('--in')+1]=str(root)+'//inputs/../inputs/.'
            argv[argv.index('--out')+1]=str(root)+'//output/.'
            # 固定 Rust create_dir_all 对尚不存在的末尾 /. 路径会失败；只验证原生允许的组合。
            output.mkdir()
            legacy=subprocess.run([BINARY,*argv],capture_output=True,text=True,timeout=30)
            self.assertEqual(legacy.returncode,0,legacy.stderr)
            text=io.StringIO();result=supervisor.execute(BINARY,argv,text)
            self.assertEqual(result['result'],'PASS');self.assertEqual(text.getvalue(),legacy.stdout)
            for p in inputs.iterdir():p.unlink()
            text=io.StringIO();result=supervisor.execute(BINARY,argv,text)
            self.assertEqual(result['result'],'PASS');self.assertEqual(text.getvalue(),'0 succeeded, 0 failed\n')
            self.assertEqual([r['tool'] for r in result['receipts']],['batch_plan','batch_complete'])

    def test_fault_after_native_save_preserves_file_and_stops_later_files(self):
        for fault in ['duplicate','nonfinite','semantic','save-array','wrong-save-path','extra-frame']:
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary);inputs,output,argv=self.prepare(root);log=root/'events.jsonl';text=io.StringIO()
                before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs.iterdir()}
                with mock.patch.dict(os.environ,CRAFT_SUPERVISED_LOG=str(log),CRAFT_SUPERVISED_FAULT=fault,CRAFT_SUPERVISED_AT='4'):
                    with self.assertRaises(Exception) as caught:
                        supervisor.execute(ROOT/'runtime/tests/fixtures/supervised_proxy.py',argv,text)
                self.assertEqual(caught.exception.outcome,'failed' if fault=='semantic' else 'unknown')
                self.assertEqual(len(caught.exception.receipts),3)
                self.assertEqual(caught.exception.lastAttempt['sequence'],4)
                self.assertTrue((output/'a.pcraft').is_file());self.assertFalse((output/'b.pcraft').exists())
                self.assertEqual(text.getvalue(),'')
                rows=[json.loads(line) for line in log.read_text().splitlines()]
                self.assertEqual([r['nativeEvent']['sequence'] for r in rows if 'nativeEvent' in r],[1,2,3,4])
                self.assertEqual([r['confirmation'] for r in rows if 'confirmation' in r],['continue 1\n','continue 2\n','continue 3\n'])
                saved=output/'a.pcraft';digest=hashlib.sha256(saved.read_bytes()).hexdigest()
                info=subprocess.run([BINARY,'info',str(saved)],capture_output=True,text=True,timeout=30)
                self.assertEqual(info.returncode,0,info.stderr)
                self.assertTrue(any(layer['name']=='Batch' for layer in json.loads(info.stdout)['layers']))
                self.assertEqual(hashlib.sha256(saved.read_bytes()).hexdigest(),digest)
                self.assertEqual({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs.iterdir()},before)

    def test_invalid_or_incomplete_native_plan_never_creates_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);_,output,argv=self.prepare(root);log=root/'events.jsonl'
            with mock.patch.dict(os.environ,CRAFT_SUPERVISED_LOG=str(log),CRAFT_SUPERVISED_FAULT='wrong-plan',CRAFT_SUPERVISED_AT='1'):
                with self.assertRaises(Exception) as caught:
                    supervisor.execute(ROOT/'runtime/tests/fixtures/supervised_proxy.py',argv,io.StringIO())
            self.assertEqual(caught.exception.outcome,'unknown');self.assertEqual(caught.exception.receipts,[])
            self.assertFalse(output.exists())
            rows=[json.loads(line) for line in log.read_text().splitlines()]
            self.assertEqual(len(rows),1);self.assertIn('nativeEvent',rows[0])

if __name__=='__main__':unittest.main()
