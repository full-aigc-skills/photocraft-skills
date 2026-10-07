"""公开计划入口必须在安装和写入前拒绝重复 JSON 键及非有限数值。"""
import json
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
DOMAIN=json.loads((ROOT/'skill-suite.json').read_text())['pluginId']
SCRIPT=ROOT/'skills'/(DOMAIN+'-use')/'scripts/commands.py'

class CommandPlanJsonTests(unittest.TestCase):
 def test_duplicate_keys_are_rejected_by_isolated_public_check(self):
  identifier=json.loads((SCRIPT.parent.parent/'references/command-coverage.json').read_text())['commands'][0]['id']
  command=json.dumps(identifier)
  cases=[
   '{"schema":"ignored","schema":"craft-command-plan/v1","operations":[{"command":'+command+',"params":{}}]}',
   '{"schema":"craft-command-plan/v1","operations":[{"command":"ignored.command","command":'+command+',"params":{}}]}',
   '{"schema":"craft-command-plan/v1","operations":[{"command":'+command+',"params":{"value":1,"value":2}}]}',
  ]
  with tempfile.TemporaryDirectory() as temporary:
   plan=Path(temporary)/'plan.json'
   for value in cases:
    with self.subTest(plan=value):
     plan.write_text(value)
     for action in ('check','run'):
      output=Path(temporary)/'output';runtime=Path(temporary)/'runtime'
      argv=[sys.executable,'-I','-B',str(SCRIPT),action,str(plan)]
      if action=='run':argv+=['--output',str(output),'--runtime-home',str(runtime)]
      result=subprocess.run(argv,capture_output=True,text=True)
      self.assertEqual(result.returncode,1,result.stdout+result.stderr)
      self.assertEqual(json.loads(result.stdout)['error'],'duplicate_json_key')
      self.assertFalse(output.exists())
      self.assertFalse(runtime.exists())
 def test_each_standalone_skill_rejects_duplicate_keys_before_install(self):
  suite=json.loads((ROOT/'skill-suite.json').read_text())
  for entry in suite['skills']:
   with self.subTest(skill=entry['name']),tempfile.TemporaryDirectory() as temporary:
    root=Path(temporary);skill=root/entry['name']
    shutil.copytree(ROOT/'skills'/entry['name'],skill,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    script=skill/'scripts/commands.py'
    identifier=json.loads((skill/'references/command-coverage.json').read_text())['commands'][0]['id']
    plan=root/'plan.json';output=root/'output';runtime=root/'runtime'
    plan.write_text('{"schema":"craft-command-plan/v1","operations":[{"command":'+json.dumps(identifier)+',"params":{"value":1,"value":2}}]}')
    rejected=subprocess.run([sys.executable,'-I','-B',str(script),'run',str(plan),'--output',str(output),'--runtime-home',str(runtime)],capture_output=True,text=True)
    self.assertEqual(rejected.returncode,1,rejected.stdout+rejected.stderr)
    self.assertEqual(json.loads(rejected.stdout)['error'],'duplicate_json_key')
    self.assertFalse(output.exists());self.assertFalse(runtime.exists())
    plan.write_text(json.dumps({'schema':'craft-command-plan/v1','operations':[{'command':identifier,'params':{}}]}))
    accepted=subprocess.run([sys.executable,'-I','-B',str(script),'check',str(plan)],capture_output=True,text=True)
    self.assertEqual(accepted.returncode,0,accepted.stdout+accepted.stderr)
    self.assertEqual(json.loads(accepted.stdout)['nativeExecution'],'NOT_RUN')
    self.assertFalse(any(skill.rglob('*.pyc')))

 def test_valid_unique_plan_remains_checkable(self):
  identifier=json.loads((SCRIPT.parent.parent/'references/command-coverage.json').read_text())['commands'][0]['id']
  with tempfile.TemporaryDirectory() as temporary:
   plan=Path(temporary)/'plan.json';plan.write_text(json.dumps({'schema':'craft-command-plan/v1','operations':[{'command':identifier,'params':{}}]}))
   result=subprocess.run([sys.executable,'-I','-B',str(SCRIPT),'check',str(plan)],capture_output=True,text=True)
   self.assertEqual(result.returncode,0,result.stdout+result.stderr)
   self.assertEqual(json.loads(result.stdout)['nativeExecution'],'NOT_RUN')

if __name__=='__main__':unittest.main()
