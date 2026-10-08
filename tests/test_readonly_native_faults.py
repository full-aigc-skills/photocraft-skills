"""真实原生只读重开后注入语义故障；原工程保全且不调度后续编辑。"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/photocraft-use/scripts'

@unittest.skipUnless(os.environ.get('CRAFT_NATIVE_PROTOCOL_FAULTS') == '1', 'explicit native readonly fault opt-in')
class ReadonlyNativeFaults(unittest.TestCase):
    def test_actual_native_reopen_faults_preserve_files_and_stop(self):
        with tempfile.TemporaryDirectory(prefix='photocraft-readonly-fault-') as temporary:
            root = Path(temporary).resolve()
            spec = importlib.util.spec_from_file_location('readonly_actual_workflow', SCRIPTS / 'workflow.py')
            workflow = importlib.util.module_from_spec(spec); spec.loader.exec_module(workflow)
            runtime = Path.home() / '.local/share/craft-runtimes'
            plan = {'document': {'width': 64, 'height': 64, 'background': 'transparent'},
                    'operations': [{'command': 'type.create', 'params': {'text': 'R', 'font': 'Arial', 'size': 12, 'x': 8, 'y': 20}}],
                    'exports': [{'format': 'png'}], 'flatExport': {'colorSpace': 'Rgb', 'transparency': 'preserve'}}
            complete = root / 'complete'; workflow.execute(plan, complete, runtime)
            partial = root / 'partial'
            with self.assertRaisesRegex(ValueError, 'flat_transparency_changed'):
                workflow.execute({**plan, 'exports': [{'format': 'jpg'}]}, partial, runtime)
            def hashes():
                return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in root.rglob('*') if p.is_file() and p.name not in {'log', 'proof', 'reply'}}
            rows = []; before = hashes()
            for verifier, output in [('checkpoint_verify', partial), ('native_verify', complete)]:
                for fault in ['open-array', 'open-index-bool', 'open-duplicate', 'inspect-missing', 'inspect-nonfinite', 'open-error', 'inspect-error']:
                    with self.subTest(verifier=verifier, fault=fault):
                        log = root / 'log'; proof = root / 'proof'; reply = root / 'reply'
                        for p in [log, proof, reply]: p.unlink(missing_ok=True)
                        args = [sys.executable, '-I', '-B', str(ROOT / 'tests/fixtures/workflow_protocol_injection.py'),
                                str(ROOT / 'tests/fixtures/readonly_protocol_proxy.py'), fault, str(log), str(proof), str(reply),
                                str(SCRIPTS / (verifier + '.py')), str(output), '--runtime-home', str(runtime)]
                        if verifier == 'checkpoint_verify': args.extend(['--write-root', str(root)])
                        result = subprocess.run(args, capture_output=True, text=True, timeout=30)
                        value = json.loads(result.stdout); self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                        self.assertEqual(value['result'], 'FAIL'); self.assertEqual(value['phase'], 'verification')
                        self.assertEqual(value['outcome'], 'failed' if fault.endswith('-error') else 'unknown')
                        self.assertFalse(value['retryable']); self.assertIn(value['recoveryAction'], ['inspect', 'reconcile'])
                        self.assertTrue(json.loads(proof.read_text())['nativeReplyReceived'])
                        calls = [r['params']['name'] for r in map(json.loads, log.read_text().splitlines()) if r.get('method') == 'tools/call']
                        self.assertEqual(calls, ['doc_open'] if fault.startswith('open-') else ['doc_open', 'doc_inspect'])
                        self.assertEqual(hashes(), before)
                        rows.append({'verifier': verifier, 'fault': fault, 'status': 'PASS', 'calls': calls,
                                     'code': value['code'], 'outcome': value['outcome'], 'filesUnchanged': True})
                args = [sys.executable, '-I', '-B', str(SCRIPTS / (verifier + '.py')), str(output), '--runtime-home', str(runtime)]
                if verifier == 'checkpoint_verify': args.extend(['--write-root', str(root)])
                healthy = subprocess.run(args, capture_output=True, text=True, timeout=30)
                self.assertEqual(healthy.returncode, 0, healthy.stdout + healthy.stderr)
                self.assertEqual(json.loads(healthy.stdout)['result'], 'PASS'); self.assertEqual(hashes(), before)
            if os.environ.get('CRAFT_READONLY_REPLY_REPORT'):
                Path(os.environ['CRAFT_READONLY_REPLY_REPORT']).write_text(json.dumps({'status': 'PASS', 'cases': rows, 'healthyVerifiers': 2,
                    'platform': 'darwin-arm64', 'filesUnchanged': True, 'scope': 'Real native read-only call then injected reply; not raw edit-streaming or creative acceptance'}, indent=2) + '\n')
