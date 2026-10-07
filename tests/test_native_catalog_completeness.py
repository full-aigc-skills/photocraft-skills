"""固定原生目录新增命令必须进入独立技能的说明与执行目录。"""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class NativeCatalogCompletenessTests(unittest.TestCase):
    def test_native_registry_and_classified_catalog_have_identical_ids(self):
        base = ROOT / 'skills/photocraft-use/references'
        snapshot = json.loads((base / 'native-command-snapshot.json').read_text())
        coverage = json.loads((base / 'command-coverage.json').read_text())
        self.assertEqual({row['id'] for row in snapshot['commands']},
                         {row['id'] for row in coverage['commands']})

    def test_new_commands_have_local_parameters_and_scene_owners(self):
        expected = {'photocraft-cli-retouch': ['brush.presets.rename', 'brush.presets.move',
                    'brush.presets.moveGroup', 'brush.presets.renameGroup', 'brush.presets.deleteGroup'],
                    'photocraft-cli-layers': ['layer.setExpanded', 'layer.setEffectsExpanded']}
        coverage = json.loads((ROOT / 'skills/photocraft-use/references/command-coverage.json').read_text())
        rows = {row['id']: row for row in coverage['commands']}
        for owner, identifiers in expected.items():
            home = ROOT / 'skills' / owner
            local = {row['id'] for row in json.loads((home / 'references/commands.json').read_text())['commands']}
            for identifier in identifiers:
                with self.subTest(command=identifier):
                    self.assertTrue(identifier in rows, 'missing command: ' + identifier)
                    self.assertEqual(rows[identifier]['ownerSkill'], owner)
                    self.assertIn(identifier, local)
                    self.assertTrue(rows[identifier]['params'])
                    self.assertIn('`' + identifier + '`', (home / 'references/scenario.md').read_text())
