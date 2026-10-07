from pathlib import Path
import json
import unittest
ROOT=Path(__file__).resolve().parents[1]
class SpecializedScenarioTests(unittest.TestCase):
 def test_independent_scenario_owns_its_command_family(self):
  domain='photocraft';name='photocraft-cli-filters';prefix='filter.'
  suite=json.loads((ROOT/'skill-suite.json').read_text());skills={r['name']:r for r in suite['skills']}
  self.assertIn(name,skills);self.assertEqual(skills[name]['kind'],'scenario')
  rows=json.loads((ROOT/'skills'/(domain+'-use')/'references/command-coverage.json').read_text())['commands'];family=[r for r in rows if r['id'].startswith(prefix)]
  self.assertTrue(family);self.assertTrue(all(r['ownerSkill']==name for r in family))
  for relative in ['SKILL.md','scripts/bootstrap.py','scripts/commands.py','scripts/runtime.lock.json']:
   self.assertTrue((ROOT/'skills'/name/relative).is_file(),relative)
if __name__=='__main__':unittest.main()
