"""单导出技能首次安装：原生可编辑图层和独立 Pillow PSD 合成图解码。"""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from test_native_workflow import product_fixture
sys.dont_write_bytecode = True


@unittest.skipUnless(os.environ.get('CRAFT_PHOTO_PSD_FIRST_USE') == '1',
                     'requires installed skill, public CLI runtime and existing Pillow')
class PsdIndependentFirstUseTests(unittest.TestCase):
    def test_masked_poster_text_revision_and_cover_have_matching_psd_composites(self):
        from PIL import Image
        with tempfile.TemporaryDirectory(prefix='craft-photo-psd-') as temporary:
            root = Path(temporary)
            skill = root / '.agents/skills/photocraft-cli-export'
            shutil.copytree(os.environ['CRAFT_INSTALLED_PHOTO_EXPORT_SKILL'], skill,
                            ignore=shutil.ignore_patterns('__pycache__'))
            self.assertEqual(len(list(skill.parent.iterdir())), 1)
            spec = importlib.util.spec_from_file_location('isolated_photo_export', skill / 'scripts/workflow.py')
            workflow = importlib.util.module_from_spec(spec); spec.loader.exec_module(workflow)
            runtime = root / 'empty-runtime'
            self.assertFalse(runtime.exists())
            image = root / 'product.png'; product_fixture(image)
            product_sha = workflow.sha(image)
            plan = json.loads((skill / 'examples/poster-plan.json').read_text())
            plan['assets'] = {'product': {'path': str(image), 'sha256': product_sha}}
            source = root / 'poster'
            first = workflow.execute(plan, source, runtime_home=runtime)
            source_hashes = self.hashes(source, workflow)
            original = self.layers(source)
            self.assertEqual(set(original), {'Product', 'Headline', 'Caption', 'Background'})
            self.assertTrue(original['Product']['hasMask'])
            self.compare_psd(source, (320, 400), Image)
            with Image.open(source / 'design.png') as poster:
                self.assertEqual(poster.convert('RGBA').getpixel((101, 150)), (250, 244, 232, 255))
                self.assertEqual(poster.convert('RGBA').getpixel((160, 220)), (233, 99, 64, 255))
            revised = root / 'revised'
            revision = {'expectedProjectSha256': first['files']['project.pcraft'], 'minimumLayers': 4,
                'operations': [{'command': 'type.edit', 'params': {'layer': {'$ref': 'headline.layer'}, 'text': 'NOVA PLUS'}}],
                'exports': plan['exports']}
            changed_manifest = workflow.execute(revision, revised, runtime_home=runtime, source=source)
            changed = self.layers(revised)
            self.assertEqual(changed['Headline']['text']['text'], 'NOVA PLUS')
            self.assertEqual(changed['Headline']['id'], original['Headline']['id'])
            for name in ['Product', 'Caption', 'Background']:
                self.assertEqual(changed[name], original[name])
            self.compare_psd(revised, (320, 400), Image)
            with Image.open(source / 'design.png') as a, Image.open(revised / 'design.png') as b:
                self.assertNotEqual(a.tobytes(), b.tobytes())
                self.assertEqual(a.crop((0, 100, 320, 400)).tobytes(), b.crop((0, 100, 320, 400)).tobytes())
            revised_hashes = self.hashes(revised, workflow)
            background = changed['Background']['id']
            cover_plan = {'expectedProjectSha256': changed_manifest['files']['project.pcraft'], 'minimumLayers': 4,
                'operations': [{'command': 'image.canvasSize', 'params': {'width': 360, 'height': 440, 'anchor': 'center', 'extensionColor': '#faf4e8'}}],
                'exports': plan['exports'], 'variant': {'width': 360, 'height': 440, 'safeArea': [8, 8, 344, 424],
                    'roles': {'background': background, 'product': {'$ref': 'product.layer'}, 'text': {'$ref': 'headline.layer'}}}}
            cover = root / 'cover'
            workflow.execute(cover_plan, cover, runtime_home=runtime, source=revised)
            self.compare_psd(cover, (360, 440), Image)
            cover_layers = self.layers(cover)
            for name in changed:
                self.assertEqual(cover_layers[name]['id'], changed[name]['id'])
                self.assertEqual(cover_layers[name]['kind'], changed[name]['kind'])
            self.assertEqual(cover_layers['Headline']['text']['text'], 'NOVA PLUS')
            self.assertTrue(cover_layers['Product']['hasMask'])
            self.assertEqual(self.hashes(source, workflow), source_hashes)
            self.assertEqual(self.hashes(revised, workflow), revised_hashes)
            self.assertEqual(workflow.sha(image), product_sha)
            self.assertFalse(any(skill.rglob('*.pyc')))

    def layers(self, directory):
        return {layer['name']: layer for layer in json.loads((directory / 'native.json').read_text())['layers']}

    def hashes(self, directory, workflow):
        return {str(path.relative_to(directory)): workflow.sha(path) for path in directory.rglob('*') if path.is_file()}

    def compare_psd(self, directory, dimensions, Image):
        with Image.open(directory / 'design.png') as png, Image.open(directory / 'design.psd') as psd:
            self.assertEqual(psd.format, 'PSD')
            self.assertEqual(png.size, dimensions)
            self.assertEqual(psd.size, dimensions)
            # Pillow exposes the merged PSD RGB image, not the editable PSD text/mask model.
            self.assertEqual(png.convert('RGBA').getchannel('A').getextrema(), (255, 255))
            self.assertEqual(png.convert('RGB').tobytes(), psd.convert('RGB').tobytes())
        native = self.layers(directory)
        psd_layers = {layer['name']: layer for layer in json.loads((directory / 'psd-inspection.json').read_text())['layers']}
        self.assertEqual(set(psd_layers), set(native))
        for name, layer in native.items():
            for field in ['kind', 'visible', 'blend', 'hasMask', 'text']:
                self.assertEqual(psd_layers[name].get(field), layer.get(field), (name, field))


if __name__ == '__main__':
    unittest.main()
