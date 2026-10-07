"""图像尺寸和模式操作必须归属已有场景并提供使用说明。"""
from pathlib import Path
import json,unittest
ROOT=Path(__file__).resolve().parents[1]
class ImageSceneRouteTests(unittest.TestCase):
 def test_image_families_route_to_existing_business_scenes(self):
  rows=json.loads((ROOT/'skills/photocraft-use/references/command-coverage.json').read_text())['commands'];owners={x['id']:x['ownerSkill'] for x in rows}
  expected={'image.trim':'photocraft-cli-resize','image.revealAll':'photocraft-cli-resize','image.rotation.arbitrary':'photocraft-cli-resize','image.duplicate':'photocraft-cli-project','image.autoTone':'photocraft-cli-adjustments','image.autoContrast':'photocraft-cli-adjustments','image.autoColor':'photocraft-cli-adjustments'}
  expected.update({x['id']:'photocraft-cli-project' for x in rows if x['id'].startswith('image.mode.')})
  self.assertEqual(len(expected),19)
  for command,owner in expected.items():
   with self.subTest(command=command):self.assertEqual(owners[command],owner)
  for skill in ['photocraft-cli-project','photocraft-cli-resize','photocraft-cli-adjustments']:
   self.assertTrue((ROOT/'skills'/skill/'references/image-transform-scene.md').is_file())
if __name__=='__main__':unittest.main()
