"""单导出技能真实 PSD 门禁：保留、已发生损失、限定接受及新会话拒绝串用。"""
import copy
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
ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.environ.get('CRAFT_PHOTO_PSD_FIRST_USE') == '1', 'explicit native PSD first-use opt-in')
class PsdPolicyFirstUseTests(unittest.TestCase):
    def test_actual_psd_loss_refusal_exact_source_acceptance_and_native_reopen(self):
        from PIL import Image
        retained = os.environ.get('CRAFT_PHOTO_PSD_POLICY_OUTPUT')
        if retained:
            root = Path(retained).resolve()
            root.mkdir(parents=True, exist_ok=False)
            self.run_native(root, Image)
        else:
            with tempfile.TemporaryDirectory(prefix='photocraft-psd-policy-') as temporary:
                self.run_native(Path(temporary), Image)

    def run_native(self, root, Image):
        installed_skill = Path(os.environ.get('CRAFT_INSTALLED_PHOTO_EXPORT_SKILL', ROOT / 'skills/photocraft-cli-export'))
        skill = root / '.agents/skills/photocraft-cli-export'
        shutil.copytree(installed_skill, skill, ignore=shutil.ignore_patterns('__pycache__'))
        spec = importlib.util.spec_from_file_location('first_use_psd_policy', skill / 'scripts/workflow.py')
        workflow = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(workflow)
        def hashes(folder):
            return {p.relative_to(folder).as_posix(): workflow.sha(p) for p in folder.rglob('*') if p.is_file()}
        skill_before = hashes(skill)
        runtime = root / 'empty-runtime'
        self.assertFalse(runtime.exists())
        product = root / 'product.png'
        product_fixture(product)
        asset = {'product': {'path': str(product), 'sha256': workflow.sha(product)}}
        poster = json.loads((skill / 'examples/poster-plan.json').read_text())
        poster['assets'] = asset
        poster['operations'].append({'command': 'native.command', 'params': {
            'command': 'layer.newAdjustmentLayer.brightnessContrast',
            'params': {'brightness': 5, 'contrast': 0, 'legacy': False}}, 'as': 'adjustment'})
        poster['psdPolicy'] = {'requiredFeatures': ['structure', 'text', 'mask', 'adjustment', 'blend', 'opacity']}
        first = root / 'poster'
        manifest = workflow.execute(poster, first, runtime, None)
        source_before = hashes(first)
        gate = json.loads((first / 'psd-acceptance.json').read_text())
        self.assertEqual(gate['status'], 'PASS')
        self.assertTrue(any(key.endswith(':adjustment') for key in gate['features']))
        with Image.open(first / 'design.png') as png, Image.open(first / 'design.psd') as psd:
            self.assertEqual(png.convert('RGB').tobytes(), psd.convert('RGB').tobytes())
        self.assertEqual(workflow.load_module('native_verify').verify(first, runtime)['result'], 'PASS')
        title = manifest['bindings']['headline']['layer']
        revision = {'expectedProjectSha256': manifest['files']['project.pcraft'],
                    'operations': [{'command': 'type.edit', 'params': {'layer': title, 'text': 'NOVA PLUS'}}],
                    'preserveObjects': {str(title): ['text.text', 'bounds']},
                    'exports': poster['exports'], 'psdPolicy': poster['psdPolicy']}
        workflow.execute(revision, root / 'poster-revised', runtime, first)
        self.assertEqual(workflow.load_module('native_verify').verify(root / 'poster-revised', runtime)['result'], 'PASS')
        self.assertEqual(hashes(first), source_before)

        background = next(layer['id'] for layer in json.loads((first / 'native.json').read_text())['layers'] if layer['name'] == 'Background')
        effect_plan = {'expectedProjectSha256': manifest['files']['project.pcraft'],
                       'operations': [{'command': 'layer.select', 'params': {'layer': background}},
                                      {'command': 'native.command', 'params': {'command': 'filter.noise.addNoise', 'params': {'amount': 12, 'seed': 4}}}],
                       'exports': poster['exports'], 'psdPolicy': {'requiredFeatures': ['effects']}}
        effect_rejected = root / 'effect-required-unknown'
        with self.assertRaisesRegex(ValueError, 'psd_required_features_unaccepted: effects'):
            workflow.execute(effect_plan, effect_rejected, runtime, first)
        effect_failure = json.loads((effect_rejected / 'failure.json').read_text())
        effect_stage = (effect_rejected / effect_failure['stage']).resolve()
        effect_gate = json.loads((effect_stage / 'psd-acceptance.json').read_text())
        self.assertEqual(effect_gate['features']['effects']['status'], 'unknown')
        with Image.open(first / 'design.png') as before, Image.open(effect_stage / 'design.png') as after:
            self.assertNotEqual(before.tobytes(), after.tobytes())
        self.assertFalse((effect_rejected / 'manifest.json').exists())
        self.assertEqual(hashes(first), source_before)

        smart_plan = {'document': {'width': 64, 'height': 64, 'background': '#ffffff'},
                      'assets': asset, 'operations': [{'command': 'asset.placeSmart', 'params': {
                          'asset': 'product', 'center': [32, 32], 'fit': False, 'scale': 100}, 'as': 'product'}],
                      'exports': [{'format': 'png'}]}
        smart = root / 'smart-source'
        smart_manifest = workflow.execute(smart_plan, smart, runtime, None)
        smart_before = hashes(smart)
        required = {'requiredFeatures': ['structure', 'smartSourceKind', 'smartTransform']}
        export_plan = {'expectedProjectSha256': smart_manifest['files']['project.pcraft'], 'operations': [],
                       'exports': [{'format': 'png'}, {'format': 'psd'}], 'psdPolicy': required}
        rejected = root / 'smart-rejected'
        with self.assertRaisesRegex(ValueError, 'psd_required_features_unaccepted'):
            workflow.execute(export_plan, rejected, runtime, smart)
        self.assertFalse((rejected / 'manifest.json').exists())
        failure = json.loads((rejected / 'failure.json').read_text())
        self.assertFalse(failure['replayAllowed'])
        stage = (rejected / failure['stage']).resolve()
        failed_gate = json.loads((stage / 'psd-acceptance.json').read_text())
        self.assertEqual(failed_gate['status'], 'FAIL')
        self.assertIn('lost', [item['status'] for item in failed_gate['features'].values()])
        self.assertIn('unknown', [item['status'] for item in failed_gate['features'].values()])
        self.assertEqual(hashes(smart), smart_before)
        stage_before = hashes(stage)
        installed = workflow.load_module('bootstrap').install(json.loads((skill / 'scripts/runtime.lock.json').read_text()), runtime)
        readonly = root / 'readonly'
        readonly.mkdir()
        with workflow.load_module('mcp_session').Session([installed['executable'], 'mcp', '--automation-read-root', str(stage), '--automation-write-root', str(readonly)]) as session:
            def call(name, args):
                return workflow.load_module('commands').parse_reply(session.request('tools/call', {'name': name, 'arguments': args}))
            call('doc_open', {'path': 'project.pcraft'})
            actual = call('doc_inspect', {})
            workflow.load_module('domain_assertions').compare(json.loads((stage / 'native.json').read_text()), actual, {})
        self.assertEqual(hashes(stage), stage_before)

        # 本测试显式接受此固定源的实际限制；产品流程不得自动生成用户接受。
        accepted = {key: {'status': failed_gate['features'][key]['status'],
                          'observationSha256': failed_gate['features'][key]['observationSha256'],
                          'reason': 'Test fixture explicitly accepts the observed smart-to-PSD limitation'}
                    for key in failed_gate['unaccepted']}
        approved_plan = {**export_plan, 'psdPolicy': {**required, 'acceptedLosses': accepted,
                         'acceptedForSourceSha256': smart_manifest['files']['project.pcraft']}}
        approved = root / 'smart-accepted'
        workflow.execute(approved_plan, approved, runtime, smart)
        approved_gate = json.loads((approved / 'psd-acceptance.json').read_text())
        self.assertEqual(approved_gate['status'], 'ACCEPTED_LOSS')
        self.assertFalse(approved_gate['completeFidelity'])
        self.assertEqual(workflow.load_module('native_verify').verify(approved, runtime)['result'], 'PASS')
        self.assertEqual(hashes(smart), smart_before)
        stale = copy.deepcopy(approved_plan)
        first_key = next(iter(stale['psdPolicy']['acceptedLosses']))
        stale['psdPolicy']['acceptedLosses'][first_key]['observationSha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'psd_required_features_unaccepted'):
            workflow.execute(stale, root / 'stale-acceptance', runtime, smart)
        wrong_source = copy.deepcopy(approved_plan)
        wrong_source['psdPolicy']['acceptedForSourceSha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'psd_acceptance_source_mismatch'):
            workflow.execute(wrong_source, root / 'wrong-source', runtime, smart)
        self.assertFalse((root / 'wrong-source').exists())

        # 即使包内摘要和门禁引用一起重算，新原生会话仍应发现串用 PSD。
        tampered = root / 'tampered'
        shutil.copytree(approved, tampered)
        shutil.copyfile(first / 'design.psd', tampered / 'design.psd')
        loss = json.loads((tampered / 'exchange-loss.json').read_text())
        psd_output = next(item for item in loss['outputs'] if item['format'] == 'psd')
        psd_output['sha256'] = workflow.sha(tampered / 'design.psd')
        accepted_gate = workflow.load_module('psd_policy').assess(loss, approved_plan['psdPolicy'], workflow.sha(tampered / 'plan.json'), approved_plan['expectedProjectSha256'])
        (tampered / 'psd-acceptance.json').write_text(json.dumps(accepted_gate, ensure_ascii=False, indent=2) + '\n')
        next(output for output in loss['outputs'] if output['format']=='psd')['observations']['psdGate']['sha256'] = workflow.sha(tampered / 'psd-acceptance.json')
        (tampered / 'exchange-loss.json').write_text(json.dumps(loss, ensure_ascii=False, indent=2) + '\n')
        tampered_manifest = json.loads((tampered / 'manifest.json').read_text())
        for name in ('design.psd', 'psd-acceptance.json', 'exchange-loss.json'):
            tampered_manifest['files'][name] = workflow.sha(tampered / name)
        tampered_manifest['lossReport']['sha256'] = workflow.sha(tampered / 'exchange-loss.json')
        (tampered / 'manifest.json').write_text(json.dumps(tampered_manifest, ensure_ascii=False, indent=2) + '\n')
        workflow.load_module('delivery').validate_delivery(tampered)
        with self.assertRaisesRegex(ValueError, 'psd_reopen_structure_changed|psd_reopen_canvas_changed'):
            workflow.load_module('native_verify').verify(tampered, runtime)
        self.assertEqual(skill_before, hashes(skill))
        self.assertEqual(hashes(smart), smart_before)
        self.assertEqual(hashes(first), source_before)
        if os.environ.get('CRAFT_PHOTO_PSD_POLICY_REPORT'):
            proof = {'schema': 'photocraft-psd-policy-first-use/v1', 'status': 'PASS',
                     'singleSkillColdInstall': True, 'nativeAndPsdFreshReopen': True,
                     'positiveFeatureMatrix': gate, 'actualLossMatrix': failed_gate,
                     'actualFilterEffectUnknownRefused': effect_gate,
                     'acceptedLossMatrix': approved_gate, 'sourceUnchanged': True,
                     'failedStageReopenedAndUnchanged': True, 'staleAcceptanceRefused': True,
                     'wrongSourceRefusedBeforeExecution': True, 'coherentHashTamperedPsdRefusedByNativeReopen': True,
                     'installedAndCopiedSkillUnchanged': True, 'driverSha256': workflow.sha(Path(__file__)),
                     'scope': 'Pinned native and PSD property/pixel tests; no Photoshop/external editor, full glyph coverage, creative or full V1 acceptance.'}
            Path(os.environ['CRAFT_PHOTO_PSD_POLICY_REPORT']).write_text(json.dumps(proof, ensure_ascii=False, indent=2) + '\n')
