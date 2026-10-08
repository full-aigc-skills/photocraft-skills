"""只读验证器不能把可解析但语义不明的原生回复当作重开成功。"""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/photocraft-use/scripts'

def load(name):
    spec = importlib.util.spec_from_file_location('readonly_test_' + name, SCRIPTS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class ReadonlyReplyContract(unittest.TestCase):
    def run_case(self, verifier, target=None, value=None):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve(); output = root / 'delivery'; output.mkdir()
            (output / 'project.pcraft').write_bytes(b'synthetic contract fixture, not native acceptance')
            (output / 'native.json').write_text(json.dumps({'width': 16, 'height': 16, 'layers': []}))
            files = {'project.pcraft': {'sha256': hashlib.sha256((output / 'project.pcraft').read_bytes()).hexdigest(), 'bytes': (output / 'project.pcraft').stat().st_size}}
            record = {'schema': 'craft-failed-stage/v1', 'stage': '.', 'files': files, 'completedOperations': 0, 'lastAttempt': None, 'replayAllowed': False}
            (output / 'failure.json').write_text(json.dumps(record))
            (output / 'manifest.json').write_text('{}')
            calls = []
            class Session:
                def __init__(self, argv): pass
                def __enter__(self): return self
                def __exit__(self, *args): pass
                def request(self, method, params):
                    name = params['name']; calls.append(name)
                    result = value if name == target else {'index': 0} if name == 'doc_open' else {'width': 16, 'height': 16, 'layers': []}
                    return {'content': [{'type': 'text', 'text': json.dumps(result)}]}
            module = load(verifier); original_load = module.load
            delivery = load('delivery')
            manifest = {'files': {'project.pcraft': files['project.pcraft']['sha256']}, 'runtimeSha256': '9' * 64}
            if verifier == 'native_verify': delivery.validate_delivery = lambda *args: manifest
            def dependency(name):
                if name == 'bootstrap': return SimpleNamespace(inspect_install=lambda *args: {'executable': 'synthetic', 'binarySha256': '9' * 64})
                if name == 'mcp_session': return SimpleNamespace(Session=Session)
                if name == 'delivery': return delivery
                if name == 'flat_export': return SimpleNamespace(verify_reopen=lambda *args: None)
                return original_load(name)
            with patch.object(module, 'load', side_effect=dependency), patch.object(module.platform, 'system', return_value='Darwin'), patch.object(module.platform, 'machine', return_value='arm64'):
                try:
                    result = module.verify(output, root, root / 'runtime') if verifier == 'checkpoint_verify' else module.verify(output, root / 'runtime')
                except RuntimeError as error:
                    return error, calls
                return result, calls

    def test_checkpoint_open_rejects_invalid_success_before_inspection(self):
        for value in [None, [], {}, {'index': True}, {'index': -1}, {'document': 0, 'index': 1}]:
            with self.subTest(value=value):
                result, calls = self.run_case('checkpoint_verify', 'doc_open', value)
                self.assertIsInstance(result, RuntimeError); self.assertEqual(calls, ['doc_open'])
                self.assertEqual(result.outcome, 'unknown')

    def test_native_open_rejects_invalid_success_before_inspection(self):
        result, calls = self.run_case('native_verify', 'doc_open', [])
        self.assertIsInstance(result, RuntimeError); self.assertEqual(calls, ['doc_open'])

    def test_checkpoint_inspection_requires_dimensions(self):
        for value in [{'layers': []}, {'width': True, 'height': 16, 'layers': []}, {'width': 0, 'height': 16, 'layers': []}]:
            with self.subTest(value=value):
                result, calls = self.run_case('checkpoint_verify', 'doc_inspect', value)
                self.assertIsInstance(result, RuntimeError); self.assertEqual(calls, ['doc_open', 'doc_inspect'])

    def test_native_inspection_requires_dimensions(self):
        result, _ = self.run_case('native_verify', 'doc_inspect', {'layers': []})
        self.assertIsInstance(result, RuntimeError)

    def test_healthy_headless_and_desktop_open_formats_remain_compatible(self):
        for verifier in ['checkpoint_verify', 'native_verify']:
            for reply in [{'index': 0}, {'path': 'project.pcraft', 'warnings': []}]:
                with self.subTest(verifier=verifier, reply=reply):
                    result, calls = self.run_case(verifier, 'doc_open', reply)
                    self.assertEqual(result['result'], 'PASS'); self.assertEqual(calls, ['doc_open', 'doc_inspect'])
