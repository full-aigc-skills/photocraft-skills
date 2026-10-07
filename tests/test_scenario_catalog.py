"""验证独立技能的完整分类清单，不把目录覆盖视作执行验收。"""
from pathlib import Path
import json
import re
import subprocess
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
class ScenarioCatalogTests(unittest.TestCase):
 def test_each_reflected_command_has_exactly_one_local_usage_entry(self):
  suite=json.loads((ROOT/'skill-suite.json').read_text());domain=suite['pluginId']
  catalog=json.loads((ROOT/'skills'/f'{domain}-use'/'references/commands.json').read_text())['commands']
  coverage=json.loads((ROOT/'skills'/f'{domain}-use'/'references/command-coverage.json').read_text())['commands']
  owners={row['id']:row['ownerSkill'] for row in coverage};observed=[]
  for skill in suite['skills']:
   if skill['kind'] not in ('scenario','cli'):continue
   home=ROOT/'skills'/skill['name'];guide=(home/'references/scenario.md').read_text()
   complete=guide.split('<!-- COMPLETE_SCENARIO_COMMANDS_START -->',1)[1].split('<!-- COMPLETE_SCENARIO_COMMANDS_END -->',1)[0]
   ids=re.findall(r'^\| `([^`]+)` \|',complete,re.M)
   for identifier in ids:
    self.assertEqual(owners[identifier],skill['name'])
    self.assertIn('## '+identifier+'\n',(home/'references/command-reference.md').read_text())
   self.assertIn('(references/scenario.md)',(home/'SKILL.md').read_text())
   observed.extend(ids)
  expected=[row['id'] for row in catalog]
  self.assertCountEqual(observed,expected)
  self.assertEqual(len(observed),len(set(observed)))
 def test_regeneration_is_current_and_read_only(self):
  paths=list((ROOT/'skills').glob('*/references/scenario.md'))
  before={p:p.read_bytes() for p in paths}
  result=subprocess.run([sys.executable,'-I','-B',str(ROOT/'scripts/build_scenario_catalog.py'),'--check'],capture_output=True,text=True)
  self.assertEqual(result.returncode,0,result.stdout+result.stderr)
  self.assertEqual(before,{p:p.read_bytes() for p in paths})
if __name__=='__main__':unittest.main()
