"""纯图片工程单技能冷启动，验证原生重开、独立 PSD 解码和字体门禁。"""
import hashlib
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


def hashes(directory):
    return {str(path.relative_to(directory)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in directory.rglob('*') if path.is_file()}


@unittest.skipUnless(os.environ.get('CRAFT_PHOTO_FONTLESS_FIRST_USE') == '1',
                     'requires public native runtime and Pillow')
class FontlessFirstUseTests(unittest.TestCase):
    def test_image_only_create_revision_and_missing_font_gate(self):
        from PIL import Image
        origin = Path(os.environ.get('CRAFT_INSTALLED_PHOTO_FONTLESS_SKILL',
                                     ROOT / 'skills/photocraft-cli-layers'))
        original_hashes = hashes(origin)
        with tempfile.TemporaryDirectory(prefix='craft-photo-fontless-') as temporary:
            root = Path(temporary)
            skill = root / '.agents/skills/photocraft-cli-layers'
            shutil.copytree(origin, skill)
            self.assertEqual(len(list(skill.parent.iterdir())), 1)
            runtime = root / 'empty-runtime'
            self.assertFalse(runtime.exists())
            image = root / 'product.png'
            Image.new('RGBA', (32, 24), (237, 52, 18, 255)).save(image)
            image_hash = hashes(root)['product.png']
            plan = {'document': {'width': 80, 'height': 60, 'background': '#faf4e8'},
                    'minimumLayers': 2,
                    'operations': [{'command': 'asset.place', 'params': {
                        'asset': 'product', 'center': [40, 30], 'name': 'Product'}, 'as': 'product'}],
                    'exports': [{'format': 'png'}, {'format': 'psd'}]}
            source = root / 'source'
            self.run_workflow(root, skill, runtime, plan, source, asset=image)
            native = json.loads((source / 'native.json').read_text())
            self.assertEqual({layer['kind'] for layer in native['layers']}, {'Pixel'})
            self.assertEqual(len(native['layers']), 2)
            with Image.open(source / 'design.png') as png, Image.open(source / 'design.psd') as psd:
                self.assertEqual(png.size, (80, 60))
                self.assertEqual(png.convert('RGB').tobytes(), psd.convert('RGB').tobytes())
                self.assertEqual(png.convert('RGBA').getpixel((40, 30)), (237, 52, 18, 255))
            source_hashes = hashes(source)
            manifest = json.loads((source / 'manifest.json').read_text())
            revision = {'expectedProjectSha256': manifest['files']['project.pcraft'],
                        'minimumLayers': 2, 'exports': plan['exports'],
                        'operations': [{'command': 'layer.select', 'params': {'layer': {'$ref': 'product.layer'}}},
                                       {'command': 'layer.renameLayer', 'params': {'name': 'Renamed Product'}}]}
            revised = root / 'revised'
            self.run_workflow(root, skill, runtime, revision, revised, source=source)
            after = json.loads((revised / 'native.json').read_text())
            self.assertEqual([x['id'] for x in after['layers']], [x['id'] for x in native['layers']])
            self.assertIn('Renamed Product', [x['name'] for x in after['layers']])
            with Image.open(revised / 'design.png') as png, Image.open(revised / 'design.psd') as psd:
                self.assertEqual(png.convert('RGB').tobytes(), psd.convert('RGB').tobytes())
            missing = dict(revision, operations=[{'command': 'type.create', 'params': {
                'text': 'Missing', 'font': 'CraftFixtureMissingFont-779c34', 'size': 12, 'x': 2, 'y': 16}}])
            result = self.run_workflow(root, skill, runtime, missing, root / 'missing-font',
                                       source=source, success=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('missing_fonts', result.stdout + result.stderr)
            self.assertFalse((root / 'missing-font/manifest.json').exists())
            failure=json.loads((root/'missing-font/failure.json').read_text())
            self.assertFalse(failure['replayAllowed']);self.assertTrue((root/'missing-font'/failure['stage']).is_dir())
            self.assertEqual(hashes(source), source_hashes)
            self.assertEqual(hashlib.sha256(image.read_bytes()).hexdigest(), image_hash)
            self.assertEqual(hashes(skill), original_hashes)
            self.assertEqual(hashes(origin), original_hashes)
            evidence = os.environ.get('CRAFT_PHOTO_FONTLESS_EVIDENCE')
            if evidence:
                Path(evidence).write_text(json.dumps({'schema': 'craft-photo-fontless-first-use/v1',
                    'runtimeSha256': manifest['runtimeSha256'], 'skillFiles': original_hashes,
                    'checks': ['single-skill-public-cold-install', 'image-only-native-reopen',
                               'independent-png-psd-pixel-match', 'revision-preserves-layer-ids',
                               'missing-font-rejected', 'source-asset-and-skills-unchanged'],
                    'excluded': ['fixed-plugin-install', 'model-dispatch', 'GUI', 'full-PSD-fidelity']},
                    ensure_ascii=False, indent=2) + '\n')

    def run_workflow(self, root, skill, runtime, plan, output, asset=None, source=None, success=True):
        path = root / (output.name + '-plan.json')
        path.write_text(json.dumps(plan))
        argv = [sys.executable, '-I', '-B', str(skill / 'scripts/workflow.py'), str(path),
                '--output', str(output), '--runtime-home', str(runtime)]
        if asset:
            argv.extend(['--asset', 'product=' + str(asset)])
        if source:
            argv.extend(['--source', str(source)])
        environment = dict(os.environ, PATH='/usr/bin:/bin:/usr/sbin:/sbin')
        for key in ('CRAFT_RUNTIME_ARCHIVE', 'CRAFT_RUNTIME_HOME'):
            environment.pop(key, None)
        result = subprocess.run(argv, capture_output=True, text=True, env=environment, timeout=180)
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result


if __name__ == '__main__':
    unittest.main()
