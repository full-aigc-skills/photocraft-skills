"""持久选区须有独立技能自带的保存、重开及局部返工计划。"""
from pathlib import Path
import json,unittest
ROOT=Path(__file__).resolve().parents[1]
class SavedSelectionSceneTests(unittest.TestCase):
 def test_saved_selection_scene_and_channel_target_prerequisites(self):
  base=ROOT/'skills/photocraft-use';p=json.loads((base/'examples/saved-selection-create.json').read_text());ids={s.get('command') for s in p['operations']}
  self.assertTrue({'select.saveSelection','select.loadSelection','select.modify.feather','channel.duplicate','channel.options','channel.rename','channel.target.composite','channel.list'}.issubset(ids))
  for name in ('reopen','revise'):
   p=json.loads((base/f'examples/saved-selection-{name}.json').read_text());self.assertEqual(p['operations'][0]['tool'],'doc_open')
  guide=(base/'references/saved-selection.md').read_text();rows=json.loads((base/'references/command-coverage.json').read_text())['commands']
  for row in rows:
   if row['ownerSkill']=='photocraft-cli-selection':self.assertIn(row['id'],guide)
if __name__=='__main__':unittest.main()
