"""编辑前元数据门禁：旧运行时或畸形能力回复不得启动编辑。"""
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('supervision_gate_test',ROOT/'skills/photocraft-use/scripts/cli_supervisor.py')
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
BINARY=os.environ.get('CRAFT_SUPERVISED_BINARY')
OLD=Path.home()/'.local/share/craft-runtimes/photocraft/0.2.0-craft.1/photocraft-cli'

class GateContracts(unittest.TestCase):
    def test_invalid_input_never_queries_runtime(self):
        with mock.patch.object(s.subprocess,'run') as query,mock.patch.object(s.subprocess,'Popen') as launch:
            with self.assertRaises(ValueError):s.execute('unused',['run','--new={"width":NaN}','--out=x.pcraft'],io.StringIO())
            query.assert_not_called();launch.assert_not_called()

    def test_malformed_missing_or_failed_capabilities_never_launch_edit(self):
        good={'schema':'photocraft-supervision-info/v1','protocol':s.SCHEMA,'runtimeVersion':'0.2.0-craft.4',
              'subcommands':['run','batch','convert'],'acknowledgment':'continue <sequence>\n'}
        cases=[('{}',0),('[]',0),(json.dumps({**good,'subcommands':['batch']}),0),
               (json.dumps({**good,'subcommands':['run','run']}),0),(json.dumps({**good,'protocol':'other'}),0),
               (json.dumps({**good,'extra':1}),0),(json.dumps(good)[:-1]+',"schema":"duplicate"}',0),
               (json.dumps(good)[:-1]+',"extra":NaN}',0),(json.dumps(good),2)]
        for reply,code in cases:
            with self.subTest(reply=reply),mock.patch.object(s.subprocess,'run',return_value=subprocess.CompletedProcess([],code,reply,'')) as query, \
                 mock.patch.object(s.subprocess,'Popen',side_effect=AssertionError('editing process launched')) as launch:
                with self.assertRaises(Exception) as caught:s.execute('unused',['run','--new={"width":32}','--out=x.pcraft'],io.StringIO())
                self.assertEqual(getattr(caught.exception,'outcome',None),'not_executed')
                self.assertEqual(getattr(caught.exception,'phase',None),'capabilities')
                self.assertFalse(caught.exception.retryable);launch.assert_not_called()
                self.assertEqual(query.call_args.args[0],['unused','--supervision-info'])

@unittest.skipUnless(BINARY,'explicit native candidate required')
class NativeGate(unittest.TestCase):
    def test_old_public_runtime_never_creates_output(self):
        self.assertTrue(OLD.is_file())
        with tempfile.TemporaryDirectory() as temporary:
            output=Path(temporary)/'never.pcraft'
            with self.assertRaises(Exception) as caught:s.execute(OLD,['run','--new={"width":32,"height":32}','--out',str(output)],io.StringIO())
            self.assertFalse(output.exists(),'old native CLI ignored supervision flag and wrote the project')
            self.assertEqual(caught.exception.outcome,'not_executed');self.assertEqual(caught.exception.phase,'capabilities')
            self.assertFalse(caught.exception.retryable)

    def test_actual_candidate_metadata_has_no_document_or_file_effects(self):
        result=subprocess.run([BINARY,'--supervision-info'],capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        info=json.loads(result.stdout)
        self.assertEqual(info['schema'],'photocraft-supervision-info/v1');self.assertEqual(info['protocol'],s.SCHEMA)
        self.assertEqual(info['subcommands'],['run','batch','convert','droplet'])
        self.assertEqual(info['acknowledgment'],'continue <sequence>\n')
        self.assertEqual(info['runtimeVersion'],os.environ.get('CRAFT_SUPERVISED_VERSION','0.2.0-craft.4'))

if __name__=='__main__':unittest.main()
