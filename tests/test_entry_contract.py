"""公开入口的无副作用拒绝、字段定位及合法动态引用合同。"""
import importlib.util
import json
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/photocraft-use/scripts'


def load(name):
    spec = importlib.util.spec_from_file_location('entry_contract_' + name, SCRIPTS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def invalid_cases(entry):
    base = {'document': {'width': 32, 'height': 32}, 'operations': []} if entry == 'workflow' else {
        'schema': 'craft-command-plan/v1', 'operations': [{'tool': 'doc_new', 'params': {'width': 32, 'height': 32}}]}
    cases = []
    def add(name, plan, path): cases.append((name, json.dumps(plan), path))
    add('unknown-root', {**base, 'typo': True}, '$.typo')
    add('container', {**base, 'operations': {}}, '$.operations')
    add('operation', {**base, 'operations': [None]}, '$.operations[0]')
    add('unknown-operation', {**base, 'operations': [{'command': 'layer.new.layer', 'params': {}, 'typo': True}]}, '$.operations[0].typo')
    add('command-type', {**base, 'operations': [{'command': [], 'params': {}}]}, '$.operations[0].command')
    add('params-container', {**base, 'operations': [{'command': 'layer.new.layer', 'params': []}]}, '$.operations[0].params')
    add('field-type', {**base, 'operations': [{'command': 'layer.select', 'params': {'layer': True}}]}, '$.operations[0].params.layer')
    add('unknown-param', {**base, 'operations': [{'command': 'layer.new.layer', 'params': {'typo': 1}}]}, '$.operations[0].params.typo')
    for name, ref in [('bad-reference', 'bad..layer'), ('missing-root', 'absent.layer'), ('future-alias', 'later.layer')]:
        add(name, {**base, 'operations': [{'command': 'layer.select', 'params': {'layer': {'$ref': ref}}}, {'command': 'layer.new.layer', 'params': {}, 'as': 'later'}]}, '$.operations[0].params.layer')
    add('alias-type', {**base, 'operations': [{'command': 'layer.new.layer', 'params': {}, 'as': []}]}, '$.operations[0].as')
    text = json.dumps(base)
    cases.extend([('duplicate-nested', text.replace('"operations":', '"nested":{"x":1,"x":2},"operations":'), '$.nested.x')])
    for name, value in [('nan', 'NaN'), ('infinity', 'Infinity'), ('negative-infinity', '-Infinity'), ('overflow', '1e999')]:
        cases.append((name, text.replace('"operations":', '"nested":{"x":' + value + '},"operations":'), '$.nested.x'))
    if entry == 'workflow':
        add('undeclared-asset', {**base, 'operations': [{'command': 'asset.place', 'params': {'asset': 'absent'}}]}, '$.operations[0].params.asset')
    return cases


class PublicEntryContractTests(unittest.TestCase):
    def test_all_entry_rejections_have_paths_and_no_files(self):
        for entry in ('workflow', 'commands', 'desktop'):
            for name, text, path in invalid_cases(entry):
                with self.subTest(entry=entry, case=name), tempfile.TemporaryDirectory() as td:
                    root = Path(td); plan = root / 'plan.json'; plan.write_text(text)
                    script = SCRIPTS / (entry + '.py')
                    argv = [sys.executable, '-I', '-B', str(script)]
                    if entry == 'commands': argv += ['run']
                    if entry == 'desktop': argv += ['run']
                    argv += [str(plan), '--output', str(root / 'output'), '--runtime-home', str(root / 'runtime')]
                    result = subprocess.run(argv, capture_output=True, text=True, timeout=30)
                    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                    reply = json.loads(result.stdout)
                    self.assertEqual(reply['phase'], 'validation')
                    self.assertEqual(reply['outcome'], 'not_executed')
                    self.assertEqual(reply['category'], 'validation_failed')
                    self.assertEqual(reply['fieldPath'], path)
                    self.assertIs(reply['retryable'], False)
                    self.assertEqual(reply['recoveryAction'], 'correct_plan')
                    self.assertEqual(sorted(p.name for p in root.iterdir()), ['plan.json'])

    def test_programmatic_wrong_alias_and_command_never_leak_type_errors(self):
        workflow = load('workflow')
        for operation, path in [({'command': [], 'params': {}}, '$.operations[0].command'),
                                ({'command': 'layer.new.layer', 'params': {}, 'as': []}, '$.operations[0].as')]:
            with self.subTest(operation=operation), self.assertRaisesRegex(ValueError, re.escape(path)):
                workflow.preflight({'document': {'width': 32, 'height': 32}, 'operations': [operation]})

    def test_future_result_fields_are_not_guessed_by_static_preflight(self):
        for name in ('workflow', 'commands'):
            plan = {'operations': [{'command': 'layer.new.layer', 'params': {}, 'as': 'layer'},
                                   {'command': 'layer.select', 'params': {'layer': {'$ref': 'layer.absent'}}}]}
            if name == 'workflow': plan['document'] = {'width': 32, 'height': 32}
            else: plan['schema'] = 'craft-command-plan/v1'
            module = load(name); module.validate(plan)
            with self.assertRaisesRegex(ValueError, 'unresolved_reference'):
                module.resolve({'$ref': 'layer.absent'}, {'layer': {'layer': 42}})

    def test_known_save_contract_does_not_bind_ambiguous_semantics(self):
        workflow = load('workflow'); commands = load('commands')
        for result in [None, [], True, 42, 'saved', {}, {'path': 42}, {'path': 'project.pcraft', 'warnings': False}]:
            reply = {'content': [{'type': 'text', 'text': json.dumps(result)}]}
            class Session:
                def request(self, *args): return reply
            state, receipts = {}, []
            with self.subTest(result=result), self.assertRaisesRegex(RuntimeError, 'outcome_unknown'):
                workflow.call_tool(Session(), 'doc_save', {'path': 'project.pcraft'}, state, receipts)
            self.assertEqual(receipts, [])
            self.assertEqual(state['lastAttempt']['phase'], 'submitted')
            with self.assertRaisesRegex(RuntimeError, 'outcome_unknown'):
                commands.validate_tool_reply('doc_save', commands.parse_reply(reply), {'path': 'project.pcraft'})

    def test_document_results_are_validated_before_success(self):
        workflow = load('workflow')
        cases = [
            ('doc_new', {'width': 32, 'height': 32}, [None, [], {}, {'document': True}, {'document': -1}, {'index': 0, 'document': 1}]),
            ('doc_open', {'path': 'source.pcraft'}, [None, {}, {'index': '0'}]),
            ('doc_inspect', {}, [None, {}, {'width': 32, 'height': 32, 'layers': [None]}]),
        ]
        for tool, args, invalid in cases:
            for result in invalid:
                class Session:
                    def request(self, *unused): return {'content': [{'type': 'text', 'text': json.dumps(result)}]}
                state, receipts = {}, []
                with self.subTest(tool=tool, result=result), self.assertRaisesRegex(RuntimeError, 'outcome_unknown'):
                    workflow.call_tool(Session(), tool, args, state, receipts)
                self.assertEqual(receipts, [])
                self.assertEqual(state['lastAttempt']['phase'], 'submitted')
        for tool, args, result in [('doc_new', {'width': 32, 'height': 32}, {'document': 0, 'extension': True}),
                                   ('doc_open', {'path': 'source.pcraft'}, {'index': 0}),
                                   ('doc_open', {'path': 'source.pcraft'}, {'path': 'source.pcraft', 'warnings': []}),
                                   ('doc_inspect', {}, {'width': 32, 'height': 32, 'layers': []})]:
            class Session:
                def request(self, *unused): return {'content': [{'type': 'text', 'text': json.dumps(result)}]}
            state, receipts = {}, []
            self.assertEqual(workflow.call_tool(Session(), tool, args, state, receipts), result)
            self.assertEqual(state['lastAttempt']['phase'], 'reply_validated')
            self.assertEqual(len(receipts), 1)
