"""PhotoCraft 单场景技能冷安装及真实像素、图层和原生重开验收。"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class TaskSkillContractTests(unittest.TestCase):
    def test_local_adjustment_skill_carries_selection_and_mask_prerequisites(self):
        rows = json.loads((ROOT / 'skills/photocraft-cli-adjustments/references/commands.json').read_text())['commands']
        required = {'layer.select', 'select.rect', 'select.deselect', 'layer.layerMask.revealSelection'}
        self.assertTrue(required.issubset({row['id'] for row in rows}))

    def test_retouch_skill_carries_target_layer_and_distinct_parameter_units(self):
        skill = ROOT / 'skills/photocraft-cli-retouch'
        rows = json.loads((skill / 'references/commands.json').read_text())['commands']
        self.assertIn('layer.select', {row['id'] for row in rows})
        guide = (skill / 'references/scenario.md').read_text()
        self.assertIn('0..1', guide)
        self.assertIn('1..100', guide)


@unittest.skipUnless(os.environ.get('CRAFT_TASK_FIRST_USE') == '1',
                     'requires macOS arm64, public CLI archives and Pillow')
class TaskSkillFirstUseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PIL import Image
        cls.temporary = tempfile.TemporaryDirectory(prefix='photocraft-task-fixture-')
        cls.fixture = Path(cls.temporary.name)
        source = ROOT / 'skills/photocraft-use'
        spec = importlib.util.spec_from_file_location('photo_task_fixture', source / 'scripts/workflow.py')
        workflow = importlib.util.module_from_spec(spec); spec.loader.exec_module(workflow)
        product = cls.fixture / 'product.png'
        Image.new('RGBA', (120, 160), (233, 99, 64, 255)).save(product)
        plan = json.loads((source / 'examples/poster-plan.json').read_text())
        plan['assets'] = {'product': {'path': str(product), 'sha256': digest(product)}}
        # 各场景从可独立编辑的无蒙版原生工程开始，不由目标技能替自己生成预期结果。
        plan['operations'] = [plan['operations'][0], *plan['operations'][4:]]
        result = workflow.execute(plan, cls.fixture / 'base', runtime_home=cls.fixture / 'fixture-runtime')
        cls.project = cls.fixture / 'base/project.pcraft'
        cls.preview = cls.fixture / 'base/design.png'
        cls.project_sha = digest(cls.project)
        cls.product = result['bindings']['product']['layer']
        cls.headline = result['bindings']['headline']['layer']

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='photocraft-task-single-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.runtime = self.root / 'fresh-runtime'
        self.environment = dict(os.environ, PATH='/usr/bin:/bin')
        self.addCleanup(lambda: self.assertEqual(digest(self.project), self.project_sha))

    def install_only(self, task):
        self.skill = self.root / '.agents/skills' / ('photocraft-cli-' + task)
        shutil.copytree(ROOT / 'skills' / self.skill.name, self.skill,
                        ignore=shutil.ignore_patterns('__pycache__'))
        self.assertEqual(len(list((self.root / '.agents/skills').iterdir())), 1)
        self.assertFalse(self.runtime.exists())

    def cli(self, *arguments, success=True):
        result = subprocess.run([sys.executable, '-I', '-B', str(self.skill / 'scripts/cli.py'),
                                 '--runtime-home', str(self.runtime), '--', *map(str, arguments)],
                                env=self.environment, capture_output=True, text=True, timeout=240)
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((self.runtime / 'photocraft' / json.loads((self.skill / 'scripts/runtime.lock.json').read_text())['resolvedVersion'] / 'photocraft-cli').is_file())
        else:
            self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(self.skill.rglob('*.pyc')))
        return result

    def execute(self, operations, target, source=None, document=None):
        argv = ['run', '--new', json.dumps(document)] if document else ['run', str(source or self.project)]
        for command, params in operations:
            argv.extend(['--cmd', command, '--params', json.dumps(params)])
        result = self.cli(*argv, '--out', target)
        rows = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
        self.assertEqual([row['command'] for row in rows], [command for command, _ in operations])
        return [row['result'] for row in rows]

    def info(self, project):
        return json.loads(self.cli('info', project).stdout)

    def layer(self, project, identifier):
        result = next(layer for layer in self.info(project)['layers'] if layer['id'] == identifier)
        # 活动选择状态改变不等于编辑旧图层的内容或属性。
        result.pop('selected', None)
        return result

    def render(self, project, name='preview.png'):
        target = self.root / name
        self.cli('convert', project, target)
        return target

    def test_project_creates_editable_layers_and_reopens_native_document(self):
        self.install_only('project')
        target = self.root / 'new.pcraft'
        results = self.execute([('layer.new.layer', {'name': 'Editable'})], target,
                           document={'name': 'Single scene', 'width': 64, 'height': 48,
                                     'mode': 'rgb', 'depth': 8, 'background': '#faf4e8'})
        reopened = self.info(target)
        self.assertEqual((reopened['width'], reopened['height'], reopened['mode'], reopened['depth']),
                         (64, 48, 'Rgb', 8))
        self.assertEqual(len(reopened['layers']), 2)
        self.assertIn(results[0]['layer'], {layer['id'] for layer in reopened['layers']})
        self.assertEqual(next(layer['name'] for layer in reopened['layers'] if layer['id'] == results[0]['layer']), 'Editable')
        self.cli('invented-subcommand', success=False)

    def test_layers_duplicate_and_edit_properties_without_mutating_original(self):
        self.install_only('layers')
        copied, target = self.root / 'copied.pcraft', self.root / 'layers.pcraft'
        original = self.layer(self.project, self.product)
        duplicate = self.execute([('layer.duplicate', {'layer': self.product})], copied)[0]['layer']
        self.execute([('layer.setProps', {'layer': duplicate, 'name': 'Product variant', 'opacity': .5})], target, copied)
        changed = self.layer(target, duplicate)
        self.assertEqual((changed['name'], changed['opacity'], changed['kind']), ('Product variant', .5, 'Pixel'))
        self.assertEqual(self.layer(target, self.product), original)
        self.assertEqual(self.layer(target, self.headline), self.layer(self.project, self.headline))

    def test_selection_limits_fill_to_requested_rectangle(self):
        from PIL import Image
        self.install_only('selection'); target = self.root / 'selection.pcraft'
        self.execute([('layer.select', {'layer': self.product}),
                  ('select.rect', {'x': 120, 'y': 160, 'width': 10, 'height': 10}),
                  ('edit.fill', {'contents': 'color', 'color': '#0033ff'})], target)
        with Image.open(self.preview) as before, Image.open(self.render(target)) as after:
            self.assertEqual(after.getpixel((125, 165))[:3], (0, 51, 255))
            self.assertEqual(before.crop((0, 180, 320, 400)).tobytes(), after.crop((0, 180, 320, 400)).tobytes())
        # 原生 pcraft 可保存活动选区；命名通道的独立备份与恢复另由场景测试核验。

    def test_mask_hides_only_requested_half_and_preserves_text(self):
        from PIL import Image
        self.install_only('masks'); target = self.root / 'mask.pcraft'
        old_text = self.layer(self.project, self.headline)
        self.execute([('layer.select', {'layer': self.product}),
                  ('select.rect', {'x': 100, 'y': 140, 'width': 60, 'height': 160}),
                  ('layer.layerMask.revealSelection', {}), ('select.deselect', {})], target)
        self.assertTrue(self.layer(target, self.product)['hasMask'])
        self.assertEqual(self.layer(target, self.headline), old_text)
        with Image.open(self.preview) as before, Image.open(self.render(target)) as after:
            self.assertEqual(after.getpixel((140, 180)), before.getpixel((140, 180)))
            self.assertNotEqual(after.getpixel((180, 180)), before.getpixel((180, 180)))
            self.assertEqual(after.crop((0, 0, 320, 100)).tobytes(), before.crop((0, 0, 320, 100)).tobytes())

    def test_adjustment_remains_editable_and_mask_limits_pixel_changes(self):
        from PIL import Image
        self.install_only('adjustments'); target = self.root / 'local-adjustment.pcraft'
        results = self.execute([('layer.select', {'layer': self.product}),
                            ('select.rect', {'x': 110, 'y': 150, 'width': 20, 'height': 20}),
                            ('layer.newAdjustmentLayer.brightnessContrast', {'brightness': 40, 'contrast': 0}),
                            ('layer.layerMask.revealSelection', {}), ('select.deselect', {})], target)
        adjustment = self.layer(target, results[2]['layer'])
        self.assertEqual(adjustment['kind'], 'Adjustment')
        self.assertTrue(adjustment['hasMask'])
        self.assertEqual(adjustment['adjustment']['BrightnessContrast']['brightness'], 40)
        with Image.open(self.preview) as before, Image.open(self.render(target)) as after:
            self.assertNotEqual(before.getpixel((115, 155)), after.getpixel((115, 155)))
            self.assertEqual(before.crop((0, 180, 320, 400)).tobytes(), after.crop((0, 180, 320, 400)).tobytes())
        self.assertEqual(self.layer(target, self.product), self.layer(self.project, self.product))

    def test_retouch_stroke_clone_and_heal_preserve_unmodified_regions(self):
        from PIL import Image
        self.install_only('retouch'); painted = self.root / 'painted.pcraft'
        result = self.execute([('layer.select', {'layer': self.product}),
                           ('paint.stroke', {'points': [[130, 180], [135, 180]], 'size': 12,
                                             'hardness': 1, 'opacity': 1, 'flow': 1, 'color': '#0033ff'})], painted)
        self.assertTrue(result[1]['damage'])
        with Image.open(self.render(painted, 'painted.png')) as image:
            self.assertEqual(image.getpixel((130, 180))[:3], (0, 51, 255))
        for command in ('paint.cloneStamp', 'paint.healingBrush'):
            target = self.root / (command.rsplit('.', 1)[1] + '.pcraft')
            result = self.execute([('layer.select', {'layer': self.product}),
                               (command, {'points': [[130, 180], [135, 180]], 'source': [140, 200],
                                          'size': 16, 'hardness': 100, 'opacity': 100, 'flow': 100})], target, painted)
            self.assertTrue(result[1]['damage'])
            with Image.open(self.preview) as before, Image.open(self.render(target, command + '.png')) as after:
                self.assertEqual(after.getpixel((130, 180))[:3], before.getpixel((130, 180))[:3])
                self.assertEqual(after.crop((0, 240, 320, 400)).tobytes(), before.crop((0, 240, 320, 400)).tobytes())
            self.assertEqual(self.layer(target, self.headline), self.layer(self.project, self.headline))

    def test_filters_blur_product_edge_and_preserve_type_and_background(self):
        from PIL import Image
        self.install_only('filters')
        target = self.root / 'filtered.pcraft'
        title = self.layer(self.project, self.headline)
        self.execute([('layer.select', {'layer': self.product}),
                      ('filter.blur.gaussianBlur', {'radius': 5})], target)
        self.assertEqual(self.layer(target, self.headline), title)
        self.assertEqual(self.layer(target, self.product)['kind'], 'Pixel')
        with Image.open(self.preview) as before, Image.open(self.render(target)) as after:
            self.assertNotEqual(before.tobytes(), after.tobytes())
            self.assertEqual(before.crop((0, 0, 320, 100)).tobytes(),
                             after.crop((0, 0, 320, 100)).tobytes())
            self.assertEqual(before.crop((0, 330, 320, 400)).tobytes(),
                             after.crop((0, 330, 320, 400)).tobytes())

    def test_text_revision_keeps_type_editable_and_product_pixels_unchanged(self):
        from PIL import Image
        self.install_only('text'); target = self.root / 'text.pcraft'
        self.execute([('type.edit', {'layer': self.headline, 'text': 'NOVA PLUS'})], target)
        title = self.layer(target, self.headline)
        self.assertEqual((title['kind'], title['text']['text']), ('Type', 'NOVA PLUS'))
        with Image.open(self.preview) as before, Image.open(self.render(target)) as after:
            self.assertNotEqual(before.crop((0, 0, 320, 100)).tobytes(), after.crop((0, 0, 320, 100)).tobytes())
            self.assertEqual(before.crop((0, 100, 320, 400)).tobytes(), after.crop((0, 100, 320, 400)).tobytes())
        self.assertEqual(self.layer(target, self.product), self.layer(self.project, self.product))

    def test_resize_generates_canvas_and_resampled_variants(self):
        from PIL import Image
        self.install_only('resize'); cover, small = self.root / 'cover.pcraft', self.root / 'small.pcraft'
        self.execute([('image.canvasSize', {'width': 400, 'height': 400, 'anchor': 'center', 'extensionColor': '#faf4e8'})], cover)
        self.execute([('image.imageSize', {'width': 160, 'height': 200, 'resolution': 72, 'resample': 'nearest'})], small)
        self.assertEqual(len(self.info(cover)['layers']), 4)
        self.assertEqual(len(self.info(small)['layers']), 4)
        with Image.open(self.preview) as original, Image.open(self.render(cover, 'cover.png')) as variant:
            self.assertEqual(variant.size, (400, 400))
            self.assertEqual(variant.crop((40, 0, 360, 400)).tobytes(), original.tobytes())
        with Image.open(self.render(small, 'small.png')) as variant:
            self.assertEqual(variant.size, (160, 200))

    def test_export_psd_preserves_layers_and_renders_same_pixels(self):
        from PIL import Image
        self.install_only('export'); psd = self.root / 'design.psd'
        self.cli('convert', self.project, psd)
        self.assertEqual(psd.read_bytes()[:4], b'8BPS')
        old = {layer['name']: layer for layer in self.info(self.project)['layers']}
        exported = self.info(psd)['layers']
        self.assertEqual({layer['name'] for layer in exported}, set(old))
        for layer in exported:
            for key in ('kind', 'text', 'visible', 'opacity', 'hasMask'):
                self.assertEqual(layer.get(key), old[layer['name']].get(key))
        with Image.open(self.preview) as before, Image.open(self.render(psd)) as after:
            self.assertEqual(before.convert('RGBA').tobytes(), after.convert('RGBA').tobytes())


if __name__ == '__main__':
    unittest.main()
