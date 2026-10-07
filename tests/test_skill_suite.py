"""单技能包隔离、非法命令边界与锁定 CLI 实际调用验收。"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
class SkillSuiteTests(unittest.TestCase):
 def test_suite_contains_separate_cli_setup_and_task_skills(self):
  suite=json.loads((ROOT/'skill-suite.json').read_text())
  names={entry['name'] for entry in suite['skills']}
  domain=suite['pluginId']
  for entry in suite['skills']:
   lock=json.loads((ROOT/'skills'/entry['name']/'scripts/runtime.lock.json').read_text())
   self.assertEqual(suite['runtimeVersion'],lock['resolvedVersion'])
  self.assertTrue({domain+'-use',domain+'-cli',domain+'-cli-setup'}.issubset(names))
  self.assertGreater(len(names),3)
  for name in names:
   with tempfile.TemporaryDirectory() as temporary:
    isolated=Path(temporary)/'only-skill';shutil.copytree(ROOT/'skills'/name,isolated,ignore=shutil.ignore_patterns('__pycache__'))
    result=subprocess.run([sys.executable,'-I','-B',str(isolated/'scripts/cli.py'),'--help'],capture_output=True,text=True)
    self.assertEqual(result.returncode,0,result.stderr)
    self.assertFalse(any(isolated.rglob('*.pyc')))
 def test_unknown_command_is_refused_before_installation(self):
  suite=json.loads((ROOT/'skill-suite.json').read_text())
  for entry in suite['skills']:
   with tempfile.TemporaryDirectory() as temporary:
    isolated=Path(temporary)/'only-skill';shutil.copytree(ROOT/'skills'/entry['name'],isolated,ignore=shutil.ignore_patterns('__pycache__'))
    runtime=Path(temporary)/'runtime'
    result=subprocess.run([sys.executable,'-I','-B',str(isolated/'scripts/cli.py'),'--runtime-home',str(runtime),'--','invented-subcommand'],capture_output=True,text=True)
    self.assertNotEqual(result.returncode,0)
    self.assertFalse(runtime.exists())

@unittest.skipUnless(os.environ.get('CRAFT_LIVE_SUITE')=='1','requires declared native CLI platform and live runtime')
class LiveSkillSuiteTests(unittest.TestCase):
 def test_every_single_skill_discovers_pinned_runtime_and_commands(self):
  suite=json.loads((ROOT/'skill-suite.json').read_text());domain=suite['pluginId']
  runtime=Path(os.environ.get('CRAFT_RUNTIME_HOME',str(Path.home()/'.local/share/craft-runtimes')))
  for entry in suite['skills']:
   with self.subTest(skill=entry['name']),tempfile.TemporaryDirectory() as temporary:
    isolated=Path(temporary)/'only-skill';shutil.copytree(ROOT/'skills'/entry['name'],isolated,ignore=shutil.ignore_patterns('__pycache__'))
    def run(*args):
     result=subprocess.run([sys.executable,'-I','-B',str(isolated/'scripts/cli.py'),'--runtime-home',str(runtime),'--',*args],capture_output=True,text=True,timeout=600)
     self.assertEqual(result.returncode,0,result.stdout+result.stderr);return result.stdout
    version=run('--version');self.assertIn('0.1.0-dev.7' if domain=='artcraft' else '0.2.0',version)
    if domain=='artcraft':
     self.assertIn('verify-package',run('--help'))
    else:
     rows=json.loads(run('commands',*(['--json'] if domain!='vectorcraft' else [])));ids={row['id'] for row in rows}
     contract=json.loads((isolated/'references/commands.json').read_text())
     self.assertTrue({row['id'] for row in contract['commands']}.issubset(ids))
    self.assertFalse(any(isolated.rglob('*.pyc')))
if __name__=='__main__':unittest.main()
