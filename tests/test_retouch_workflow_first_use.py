"""独立修图技能公开工作流：真实笔触、保护区域、另存和冷安装。"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
ROOT = Path(__file__).resolve().parents[1]

@unittest.skipUnless(os.environ.get('CRAFT_RETOUCH_WORKFLOW_FIRST_USE') == '1', 'requires native online first use')
class RetouchWorkflowFirstUse(unittest.TestCase):
    def test_stroke_clone_heal_and_protected_rejection(self):
        with tempfile.TemporaryDirectory(prefix='photo-retouch-workflow-') as temp:
            root = Path(temp)
            source = Path(os.environ.get('CRAFT_INSTALLED_RETOUCH_SKILL_ROOT', ROOT / 'skills/photocraft-cli-retouch'))
            skill = root / 'only-retouch'; shutil.copytree(source, skill, ignore=shutil.ignore_patterns('__pycache__'))
            spec = importlib.util.spec_from_file_location('retouch_png', skill / 'scripts/pixel_guard.py')
            guard = importlib.util.module_from_spec(spec); spec.loader.exec_module(guard)
            def chunk(kind, data):
                return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
            image = root / 'product.png'
            image.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 120, 160, 8, 6, 0, 0, 0)) + chunk(b'IDAT', zlib.compress((b'\0' + bytes([233, 99, 64, 255]) * 120) * 160)) + chunk(b'IEND', b''))
            environment = {**os.environ, 'PATH': '/usr/bin:/bin'}
            environment.pop('CRAFT_RUNTIME_HOME', None)
            runtime = root / 'fresh-runtime'
            def run(plan, output, prior=None, asset=False):
                file = root / (output.name + '.json'); file.write_text(json.dumps(plan))
                args = [sys.executable, '-I', '-B', str(skill / 'scripts/workflow.py'), str(file), '--output', str(output), '--runtime-home', str(runtime)]
                if prior: args.extend(['--source', str(prior)])
                if asset: args.extend(['--asset', 'product=' + str(image)])
                result = subprocess.run(args, capture_output=True, text=True, env=environment, timeout=180)
                return result
            def hashes(directory):
                return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.iterdir() if p.is_file()}
            plan = json.loads((skill / 'examples/poster-plan.json').read_text())
            original = root / 'original'; first = run(plan, original, asset=True)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            manifest = json.loads(first.stdout); originals = hashes(original)
            selected = {'command': 'layer.select', 'params': {'layer': {'$ref': 'product.layer'}}}
            stroke = {'command': 'paint.stroke', 'params': {'points': [[130, 180], [135, 180]], 'size': 12, 'hardness': 1, 'opacity': 1, 'flow': 1, 'color': '#0033ff'}}
            def revision(prior_manifest, operation, regions):
                return {'expectedProjectSha256': prior_manifest['files']['project.pcraft'], 'minimumLayers': 4, 'operations': [selected, operation], 'exports': [{'format': 'png'}, {'format': 'psd'}], 'protectedRegions': regions}
            protected = [{'id': 'header', 'rect': [0, 0, 320, 100]}, {'id': 'footer', 'rect': [0, 240, 320, 160]}]
            painted = root / 'painted'; result = run(revision(manifest, stroke, protected), painted, original)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            painted_manifest = json.loads(result.stdout); painted_hashes = hashes(painted)
            def pixel(path, x, y):
                width, height, data, profiles = guard.decode(path); index = (y * width + x) * 4
                return tuple(data[index:index + 4])
            self.assertEqual(pixel(painted / 'design.png', 130, 180), (0, 51, 255, 255))
            observations = {}
            for command in ('paint.cloneStamp', 'paint.healingBrush'):
                operation = {'command': command, 'params': {'points': [[130, 180], [135, 180]], 'source': [140, 200], 'size': 16, 'hardness': 100, 'opacity': 100, 'flow': 100}}
                target = root / command.rsplit('.', 1)[1]
                result = run(revision(painted_manifest, operation, protected), target, painted)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(pixel(target / 'design.png', 130, 180), pixel(original / 'design.png', 130, 180))
                operations = json.loads((target / 'operations.json').read_text())
                self.assertTrue(next(item['result']['damage'] for item in operations if item['arguments'].get('id') == command))
                report = json.loads((target / 'pixel-protection.json').read_text())
                self.assertTrue(all(region['changedPixels'] == 0 for region in report['regions']))
                self.assertEqual(len(json.loads((target / 'psd-inspection.json').read_text())['layers']), len(json.loads((target / 'native.json').read_text())['layers']))
                observations[command] = {'files': json.loads(result.stdout)['files'], 'protection': report}
            rejected = root / 'rejected'
            result = run(revision(manifest, stroke, [{'id': 'stroke-target', 'rect': [120, 170, 30, 30]}]), rejected, original)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn('protected_region_changed', result.stdout); self.assertFalse(rejected.exists())
            self.assertEqual(originals, hashes(original)); self.assertEqual(painted_hashes, hashes(painted))
            self.assertFalse(list(skill.rglob('*.pyc')))
            if os.environ.get('CRAFT_RETOUCH_EVIDENCE_FILE'):
                with Path(os.environ['CRAFT_RETOUCH_EVIDENCE_FILE']).open('x') as output:
                    json.dump({'schema': 'photocraft-retouch-workflow-first-use/v1', 'python': sys.version.split()[0], 'runtimeSha256': manifest['runtimeSha256'], 'sourceFiles': originals, 'paintedFiles': painted_manifest['files'], 'operations': observations, 'protectedStrokeRejected': True, 'allSourceFilesPreserved': True, 'scope': 'single copied skill, fresh online install, system-only PATH; bounded solid-colour fixture, no creative quality acceptance'}, output, indent=2)
                    output.write('\n')

if __name__ == '__main__': unittest.main()
