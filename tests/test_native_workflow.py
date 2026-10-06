"""原生图层、蒙版、改字保护区域与 PSD 交换的真实验收。"""
import hashlib
import importlib.util
import sys

# 宿主技能快照必须保持不可变；动态导入也不写字节码。
sys.dont_write_bytecode = True
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
SKILL = Path(os.environ['CRAFT_INSTALLED_SKILL_ROOT']).resolve() if os.environ.get('CRAFT_INSTALLED_SKILL_ROOT') else ROOT / 'skills/photocraft-use'
SCRIPTS = SKILL / 'scripts'

def product_fixture(path):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    raw = b''.join(b'\0' + bytes([233, 99, 64, 255]) * 120 for _ in range(160))
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 120, 160, 8, 6, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))

@unittest.skipUnless(os.environ.get('CRAFT_LIVE_TEST') == '1', 'requires real CLI and Pillow for pixel acceptance')
class NativeWorkflowTests(unittest.TestCase):
    def test_layer_mask_text_revision_psd_and_size_variant(self):
        from PIL import Image
        spec = importlib.util.spec_from_file_location('workflow', SCRIPTS / 'workflow.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / 'product.png'
            product_fixture(product)
            plan = json.loads((SKILL / 'examples/poster-plan.json').read_text())
            plan['assets'] = {'product': {'path': str(product), 'sha256': module.sha(product)}}
            # 无蒙版版本提供保护区域的真实对照。
            mask_operations = plan['operations'][1:4]
            plan['operations'] = [plan['operations'][0], *plan['operations'][4:]]
            first = root / 'original'
            initial = module.execute(plan, first)
            native = json.loads((first / 'native.json').read_text())
            self.assertEqual(len(native['layers']), 4)
            self.assertEqual({x['kind'] for x in native['layers']}, {'Pixel', 'Type'})
            revision = {'expectedProjectSha256': initial['files']['project.pcraft'], 'minimumLayers': 4,
                        'operations': [{'command': 'layer.select', 'params': {'layer': {'$ref': 'product.layer'}}}, *mask_operations], 'exports': plan['exports']}
            masked = root / 'masked'
            manifest = module.execute(revision, masked, source=first)
            after = json.loads((masked / 'native.json').read_text())
            by_name = {x['name']: x for x in after['layers']}
            self.assertTrue(by_name['Product']['hasMask'])
            with Image.open(first / 'design.png') as a, Image.open(masked / 'design.png') as b:
                a.load(); b.load()
                self.assertEqual(a.size, (320, 400))
                self.assertEqual(a.crop((0, 0, 320, 100)).tobytes(), b.crop((0, 0, 320, 100)).tobytes())
                self.assertNotEqual(a.getpixel((101, 150)), b.getpixel((101, 150)))
                self.assertEqual(a.getpixel((160, 220)), b.getpixel((160, 220)))
            # PSD 以语义比对，不假设交换格式重新分配的图层 ID 相同。
            psd = json.loads((masked / 'psd-inspection.json').read_text())
            for layer in psd['layers']:
                original = by_name[layer['name']]
                for field in ['kind', 'visible', 'blend', 'hasMask', 'text']:
                    self.assertEqual(layer.get(field), original.get(field))
            installed = module.load_module('bootstrap').install(
                json.loads((SCRIPTS / 'runtime.lock.json').read_text()),
                os.environ.get('CRAFT_RUNTIME_HOME', str(Path.home() / '.local/share/craft-runtimes')))
            decoded = root / 'psd-decoded.png'
            subprocess.run([installed['executable'], 'convert', str(masked / 'design.psd'), str(decoded)], check=True, capture_output=True, timeout=120)
            with Image.open(masked / 'design.png') as a, Image.open(decoded) as b:
                self.assertEqual(a.convert('RGBA').tobytes(), b.convert('RGBA').tobytes())
            revision['expectedProjectSha256'] = manifest['files']['project.pcraft']
            revision['operations'] = [{'command': 'type.edit', 'params': {'layer': {'$ref': 'headline.layer'}, 'text': 'NOVA PLUS'}}]
            changed = root / 'changed'
            changed_manifest = module.execute(revision, changed, source=masked)
            with Image.open(masked / 'design.png') as a, Image.open(changed / 'design.png') as b:
                self.assertNotEqual(a.tobytes(), b.tobytes())
                self.assertEqual(a.crop((0, 100, 320, 400)).tobytes(), b.crop((0, 100, 320, 400)).tobytes())
            self.assertEqual(changed_manifest['assets'], manifest['assets'])
            cover = dict(revision, operations=[{'command': 'image.canvasSize', 'params': {'width': 400, 'height': 400, 'anchor': 'center', 'extensionColor': '#faf4e8'}}])
            module.execute(cover, root / 'cover', source=masked)
            with Image.open(root / 'cover/design.png') as image:
                self.assertEqual(image.size, (400, 400))
            self.assertEqual(module.sha(masked / 'project.pcraft'), manifest['files']['project.pcraft'])
            missing_font = dict(revision, operations=[{'command': 'type.setStyle', 'params': {'layer': {'$ref': 'headline.layer'}, 'font': 'CraftFixtureMissingFont-779c34'}}])
            with self.assertRaisesRegex(ValueError, 'missing_fonts'):
                module.execute(missing_font, root / 'missing-font', source=masked)
            failure = json.loads((root / 'missing-font/failure.json').read_text())
            self.assertEqual(failure['status'], 'failed')
            self.assertIn('missing_fonts', failure['error'])
            self.assertFalse(failure['replayAllowed'])
            self.assertTrue((root / 'missing-font' / failure['stage']).is_dir())
            self.assertFalse((root / 'missing-font/manifest.json').exists())
            self.assertEqual(module.sha(masked / 'project.pcraft'), manifest['files']['project.pcraft'])
            revision['expectedProjectSha256'] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'revision_conflict'):
                module.execute(revision, root / 'invalid', source=masked)
            plan['assets']['product']['sha256'] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'asset_checksum_mismatch'):
                module.execute(plan, root / 'invalid-asset')

if __name__ == '__main__':
    unittest.main()
