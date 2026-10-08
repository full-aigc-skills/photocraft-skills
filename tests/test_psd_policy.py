"""必要 PSD 功能与精确损失接受门禁；静态夹具不充当原生保真证据。"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/photocraft-use/scripts'


def load(name):
    spec = importlib.util.spec_from_file_location('policy_test_' + name, SCRIPTS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PsdPolicyTests(unittest.TestCase):
    def report(self):
        return {'native': {'location': 'project.pcraft', 'sha256': 'a' * 64},
                'inspection': {'location': 'native.json', 'sha256': 'b' * 64},
                'psdInspection': {'location': 'psd-inspection.json', 'sha256': 'c' * 64},
                'outputs': [{'location': 'design.psd', 'sha256': 'd' * 64, 'format': 'psd',
                             'observations': {'featureMatrix': {'features': {
                                 '0:structure': {'status': 'retained'},
                                 '0:text': {'status': 'degraded', 'native': {'text': '中文'}, 'psd': {'text': '中'}},
                                 'effects': {'status': 'unknown'}}}}}]}

    def test_known_loss_and_required_unknown_refuse_without_acceptance(self):
        policy = load('psd_policy')
        report = self.report()
        gate = policy.assess(report, {'requiredFeatures': ['text', 'effects']}, 'e' * 64)
        self.assertEqual(gate['status'], 'FAIL')
        self.assertEqual(set(gate['unaccepted']), {'0:text', 'effects'})
        self.assertEqual(set(policy.assess(report, {}, 'e' * 64)['unaccepted']), {'0:text'})
        self.assertFalse(gate['completeFidelity'])

    def test_acceptance_is_exact_to_observation_and_status_and_never_fidelity(self):
        policy = load('psd_policy')
        report = self.report()
        gate = policy.assess(report, {'requiredFeatures': ['*']}, 'e' * 64)
        accepted = {key: {'status': gate['features'][key]['status'],
                          'observationSha256': gate['features'][key]['observationSha256'],
                          'reason': 'Test-only explicit acceptance of this reported limitation'} for key in gate['unaccepted']}
        plan = {'requiredFeatures': ['*'], 'acceptedLosses': accepted, 'acceptedForSourceSha256': 'f' * 64}
        approved = policy.assess(report, plan, 'e' * 64, 'f' * 64)
        self.assertEqual(approved['status'], 'ACCEPTED_LOSS')
        self.assertFalse(approved['completeFidelity'])
        self.assertEqual(approved['native'], report['native'])
        self.assertEqual(approved['psd']['sha256'], 'd' * 64)
        self.assertEqual(approved['planSha256'], 'e' * 64)
        changed = copy.deepcopy(report)
        changed['outputs'][0]['observations']['featureMatrix']['features']['0:text']['native']['text'] = '另一个标题'
        self.assertEqual(policy.assess(changed, plan, 'e' * 64, 'f' * 64)['status'], 'FAIL')
        wrong = copy.deepcopy(plan)
        wrong['acceptedLosses']['0:text']['status'] = 'lost'
        self.assertEqual(policy.assess(report, wrong, 'e' * 64, 'f' * 64)['status'], 'FAIL')
        self.assertEqual(policy.assess(report, plan, 'e' * 64, 'a' * 64)['status'], 'FAIL')

    def test_unobserved_required_feature_and_unused_approval_cannot_pass(self):
        policy = load('psd_policy')
        report = self.report()
        gate = policy.assess(report, {'requiredFeatures': ['mask']}, 'e' * 64)
        self.assertEqual(gate['status'], 'FAIL')
        self.assertIn('mask', gate['unobservedRequired'])
        accepted = {'99:text': {'status': 'lost', 'observationSha256': 'f' * 64, 'reason': 'stale candidate'}}
        gate = policy.assess(report, {'acceptedLosses': accepted, 'acceptedForSourceSha256': 'f' * 64}, 'e' * 64, 'f' * 64)
        self.assertIn('99:text', gate['unusedAcceptances'])
        self.assertEqual(gate['status'], 'FAIL')

    def test_structural_acceptance_hash_includes_actual_kind_and_name(self):
        features = load('psd_features')
        policy = load('psd_policy')
        original = {'layers': [{'name': 'Product', 'kind': 'Smart Object'}]}
        exported = {'layers': [{'name': 'Product', 'kind': 'Pixel'}]}
        first = features.assess(original, exported)['features']['0:structure']
        second = features.assess({'layers': [{'name': 'Another', 'kind': 'Type'}]}, exported)['features']['0:structure']
        self.assertNotEqual(policy.digest(first), policy.digest(second))

    def test_psd_reopen_allows_new_ids_but_not_semantic_or_canvas_changes(self):
        features = load('psd_features')
        first = {'width': 32, 'height': 16, 'mode': 'Rgb', 'depth': 8, 'layers': [
            {'id': 1, 'kind': 'Group', 'name': 'Group', 'selected': False, 'children': [
                {'id': 2, 'kind': 'Type', 'name': 'Title', 'text': {'text': '中文'}, 'hasMask': True}]}]}
        fresh = copy.deepcopy(first)
        fresh['layers'][0]['id'] = 30
        fresh['layers'][0]['selected'] = True
        fresh['layers'][0]['children'][0]['id'] = 31
        features.verify_reopen(first, fresh)
        changed = copy.deepcopy(fresh)
        changed['layers'][0]['children'][0]['text']['text'] = '其他'
        with self.assertRaisesRegex(ValueError, 'psd_reopen_structure_changed'):
            features.verify_reopen(first, changed)
        with self.assertRaisesRegex(ValueError, 'psd_reopen_canvas_changed'):
            features.verify_reopen(first, {**fresh, 'width': 64})

    def test_invalid_policy_is_rejected_before_installation_or_output(self):
        workflow = load('workflow')
        base = {'document': {'width': 16, 'height': 16}, 'operations': [], 'exports': [{'format': 'psd'}]}
        bad = [None, {'requiredFeatures': 'text'}, {'requiredFeatures': ['text', 'text']},
               {'requiredFeatures': ['invented']}, {'acceptedLosses': []}, {'typo': True},
               {'acceptedLosses': {'0:text': {'status': 'retained', 'observationSha256': 'f' * 64, 'reason': 'wrong'}}}]
        for value in bad:
            with self.subTest(value=value), tempfile.TemporaryDirectory() as temporary:
                with self.assertRaisesRegex(ValueError, 'invalid_psd_policy'):
                    workflow.execute({**base, 'psdPolicy': value}, Path(temporary) / 'out', Path(temporary) / 'runtime')
                self.assertEqual(list(Path(temporary).iterdir()), [])
        with self.assertRaisesRegex(ValueError, 'psd_policy_requires_psd'):
            workflow.validate({**base, 'exports': [], 'psdPolicy': {'requiredFeatures': ['text']}})

    def test_exchange_report_preserves_loss_and_native_before_refusing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'project.pcraft').write_bytes(b'fixture native project')
            (root / 'design.psd').write_bytes(b'fixture PSD, not a native test')
            (root / 'native.json').write_text(json.dumps({'layers': [{'name': 'Title', 'kind': 'Type', 'text': {'text': '标题'}}]}))
            (root / 'psd-inspection.json').write_text(json.dumps({'layers': [{'name': 'Title', 'kind': 'Pixel'}]}))
            (root / 'plan.json').write_text(json.dumps({'operations': [], 'exports': [{'format': 'psd'}]}))
            with self.assertRaisesRegex(ValueError, 'psd_required_features_unaccepted'):
                load('exchange_loss').write_report(root, ['design.psd'], {})
            self.assertTrue((root / 'project.pcraft').exists())
            self.assertTrue((root / 'exchange-loss.json').exists())
            self.assertEqual(json.loads((root / 'psd-acceptance.json').read_text())['status'], 'FAIL')
            self.assertFalse((root / 'manifest.json').exists())

    def test_delivery_refuses_missing_gate_even_when_all_file_hashes_match(self):
        # 使用普通有效包结构；仅缺少计划要求的 PSD 门禁应拒绝。
        delivery = load('delivery')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            native = {'layers': [{'name': 'Title', 'kind': 'Type', 'text': {'text': '标题'}}]}
            for filename, value in [('native.json', native), ('psd-inspection.json', native),
                                    ('operations.json', []), ('plan.json', {'operations': [], 'exports': [{'format': 'psd'}], 'psdPolicy': {'requiredFeatures': ['text']}})]:
                (root / filename).write_text(json.dumps(value))
            (root / 'project.pcraft').write_bytes(b'native fixture')
            (root / 'design.psd').write_bytes(b'PSD fixture')
            load('exchange_loss').write_report(root, ['design.psd'], {})
            loss = json.loads((root / 'exchange-loss.json').read_text())
            loss.pop('psdGate', None)
            for output in loss['outputs']:output.get('observations',{}).pop('psdGate',None)
            (root / 'exchange-loss.json').write_text(json.dumps(loss))
            (root / 'psd-acceptance.json').unlink(missing_ok=True)
            files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir()}
            manifest = {'schema': 'photocraft-delivery/v1', 'files': files, 'assets': {},
                        'outputs': [{'path': 'design.psd'}], 'lossReport': {'path': 'exchange-loss.json', 'sha256': files['exchange-loss.json']}}
            (root / 'manifest.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'delivery_psd_gate_missing'):
                delivery.validate_delivery(root)
