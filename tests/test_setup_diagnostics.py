"""首次安装失败必须保留错误并定位当前技能自身的恢复入口。"""
from pathlib import Path
import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
class SetupFailureTests(unittest.TestCase):
 def test_public_bootstrap_failure_identifies_own_setup_without_retry(self):
  domain=json.loads((ROOT/'skill-suite.json').read_text())['pluginId']
  path=ROOT/'skills'/f'{domain}-use'/'scripts/bootstrap.py'
  spec=importlib.util.spec_from_file_location('setup_failure_boot',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  installer='install_node' if domain=='artcraft' else 'install'
  with tempfile.TemporaryDirectory(prefix='craft setup space ') as temporary:
   runtime=Path(temporary)/'runtime';output=io.StringIO()
   with patch.object(sys,'argv',[str(path),'--runtime-home',str(runtime)]),patch.object(module,installer,side_effect=ValueError('unsupported_platform: fixture')) as install,contextlib.redirect_stdout(output):
    with self.assertRaises(SystemExit) as exit:module.main()
   self.assertEqual(exit.exception.code,1);self.assertEqual(install.call_count,1)
   reply=json.loads(output.getvalue());self.assertEqual(reply['error'],'unsupported_platform: fixture')
   setup=reply['dependencySetup'];self.assertEqual(setup['skill'],domain+'-cli-setup')
   self.assertEqual(setup['bootstrapScript'],str(path.resolve()));self.assertEqual(setup['runtimeHome'],str(runtime))
   self.assertFalse(setup['automaticRetry']);self.assertFalse(runtime.exists())

 def test_native_failure_is_not_reported_as_missing_dependency(self):
  from types import SimpleNamespace
  domain=json.loads((ROOT/'skill-suite.json').read_text())['pluginId']
  path=ROOT/'skills'/f'{domain}-use'/'scripts/cli.py'
  spec=importlib.util.spec_from_file_location('setup_failure_cli',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  output=io.StringIO()
  with patch.object(sys,'argv',[str(path),'--','--version']),contextlib.redirect_stdout(output):
   if domain=='artcraft':
    receipt=SimpleNamespace(returncode=0,stdout=json.dumps({'nodeExecutable':'fixture-node','entryPoint':'fixture-entry'}))
    with patch.object(module.subprocess,'run',side_effect=[receipt,OSError('native_fixture_failure')]) as run:code=module.main()
    self.assertEqual(run.call_count,2)
   else:
    boot=SimpleNamespace(install=lambda *args:{'executable':'fixture-cli'},setup_failure=lambda *args:(_ for _ in ()).throw(AssertionError('incorrect setup diagnostic')))
    mocked=SimpleNamespace(loader=SimpleNamespace(exec_module=lambda module:None))
    with patch.object(module.importlib.util,'spec_from_file_location',return_value=mocked),patch.object(module.importlib.util,'module_from_spec',return_value=boot),patch.object(module.subprocess,'run',side_effect=OSError('native_fixture_failure')) as run:code=module.main()
    self.assertEqual(run.call_count,1)
  self.assertEqual(code,1);reply=json.loads(output.getvalue());self.assertEqual(reply['error'],'native_fixture_failure');self.assertNotIn('dependencySetup',reply)


 def test_missing_lock_in_single_skill_returns_local_diagnostic(self):
  import shutil
  import subprocess
  domain=json.loads((ROOT/'skill-suite.json').read_text())['pluginId']
  source=ROOT/'skills'/f'{domain}-use'/'scripts/bootstrap.py'
  with tempfile.TemporaryDirectory(prefix='craft missing lock ') as temporary:
   home=Path(temporary)/'one skill';scripts=home/'scripts';scripts.mkdir(parents=True);path=scripts/'bootstrap.py';shutil.copyfile(source,path);runtime=Path(temporary)/'runtime'
   result=subprocess.run([sys.executable,'-I','-B',str(path),'--runtime-home',str(runtime)],capture_output=True,text=True)
   self.assertEqual(result.returncode,1,result.stdout+result.stderr)
   reply=json.loads(result.stdout);self.assertEqual(reply['dependencySetup']['bootstrapScript'],str(path.resolve()));self.assertFalse(reply['dependencySetup']['automaticRetry']);self.assertFalse(runtime.exists());self.assertNotIn('Traceback',result.stderr)

if __name__=='__main__':unittest.main()
