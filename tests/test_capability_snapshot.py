import importlib.util
import json
from pathlib import Path
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/photocraft-use/scripts'

def module():
    spec = importlib.util.spec_from_file_location('capabilities', SCRIPTS/'capabilities.py')
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value); return value

class CapabilityTests(unittest.TestCase):
    def test_same_id_changed_parameters_invalidate_snapshot(self):
        m = module()
        a = m.snapshot([{'id':'type.edit','params':'{"text": string}','enabled':True}], [{'name':'command_run','inputSchema':{'type':'object'}}], 'a'*64, 'headless', 'session-1')
        b = m.snapshot([{'id':'type.edit','params':'{"title": string}','enabled':True}], [{'name':'command_run','inputSchema':{'type':'object'}}], 'a'*64, 'headless', 'session-1')
        with self.assertRaisesRegex(ValueError, 'capability_changed'):m.ensure(a,b)
        with self.assertRaisesRegex(ValueError, 'capability_changed'):m.ensure(a,{**a,'sessionId':'session-2'})
    def test_enabled_is_dynamic_but_schema_and_backend_are_bound(self):
        m = module(); rows=[{'id':'x','params':'{}','enabled':True}]; tools=[{'name':'command_run','inputSchema':{'type':'object'}}]
        a=m.snapshot(rows,tools,'a'*64,'headless','s')
        b=m.snapshot([{**rows[0],'enabled':False}],tools,'a'*64,'headless','s')
        m.ensure(a,b)
        with self.assertRaisesRegex(ValueError,'capability_changed'):m.ensure(a,{**b,'backend':'bridge'})
    def test_catalog_parameter_drift_is_not_id_coverage(self):
        m=module()
        with self.assertRaisesRegex(ValueError,'catalog_parameter_drift'):m.match_catalog([{'id':'x','params':'{"a":int}'}],[{'id':'x','params':'{"b":int}'}])

class BackendCapabilityTests(unittest.TestCase):
 def test_bridge_uses_its_pinned_registry_and_rejects_content_drift(self):
  m=module();rows=[{'id':'file.new','params':'{}','enabled':True}];tools=[{'name':'command_run','inputSchema':{'type':'object'}}]
  class Commands:
   def runtime_rows(self,session):return session.rows
   def catalog(self):return {'commands':rows+[{'id':'headless.only','params':'{}'}]}
  class Session:
   def __init__(self):self.rows=rows
   def request(self,method,params):return {'tools':tools}
  pinned={'cliBinarySha256':'a'*64,'desktopBinarySha256':'b'*64,'commands':rows,'tools':tools}
  session=Session();gate=m.Gate(session,Commands(),'a'*64,'bridge',reference=pinned)
  self.assertEqual(gate.check()['commandCount'],1)
  session.rows=[{**rows[0],'params':'{"changed":int}'}]
  with self.assertRaisesRegex(ValueError,'capability_changed'):gate.check()

 def test_desktop_only_unavailable_command_is_rejected_before_install(self):
  import tempfile
  spec=importlib.util.spec_from_file_location('backend_commands',SCRIPTS/'commands.py');commands=importlib.util.module_from_spec(spec);spec.loader.exec_module(commands)
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary);token=root/'token';token.write_text('test-only-token')
   def install(*args):self.fail('backend-incompatible plan reached installation')
   plan={'schema':'craft-command-plan/v1','operations':[{'command':'layer.setExpanded','params':{'layer':1,'expanded':True}}]}
   batch={'schema':'craft-command-plan/v1','operations':[{'tool':'command_batch','params':{'steps':[{'id':'layer.setExpanded','params':{'layer':1,'expanded':True}}]}}]}
   for candidate in (plan,batch):
    with self.assertRaisesRegex(ValueError,'backend_command_unavailable'):commands.execute(candidate,root/'output',mode='bridge',connect='127.0.0.1:12345',token_file=str(token),installer=install)
   self.assertFalse((root/'output').exists())

class RuntimeIdentityTests(unittest.TestCase):
 def test_snapshot_binds_version_platform_and_detects_same_binary_metadata_drift(self):
  m=module();rows=[{'id':'x','params':'{}','enabled':True}];tools=[{'name':'command_run','inputSchema':{'type':'object'}}]
  identity={'version':'0.2.0-craft.1','versionOutput':'photocraft-cli 0.2.0-craft.1 (dev build)','platform':'darwin-arm64'}
  a=m.snapshot(rows,tools,'a'*64,'headless','s',runtime_identity=identity)
  self.assertEqual(a['runtimeIdentity'],identity)
  for key,value in [('version','0.2.0'),('platform','darwin-x86_64'),('versionOutput','different build')]:
   b=m.snapshot(rows,tools,'a'*64,'headless','s',runtime_identity={**identity,key:value})
   with self.assertRaisesRegex(ValueError,'capability_mismatch'):m.ensure(a,b)
 def test_invalid_runtime_identity_cannot_be_recorded_as_verified(self):
  m=module();rows=[];tools=[]
  for identity in [{},{'version':True,'versionOutput':'x','platform':'darwin-arm64'},{'version':'0.2.0','versionOutput':'x','platform':'unknown'}]:
   with self.subTest(identity=identity),self.assertRaisesRegex(ValueError,'runtime_identity_invalid'):m.snapshot(rows,tools,'a'*64,'headless','s',runtime_identity=identity)
 def test_missing_command_and_same_id_schema_drift_use_contract_error_codes(self):
  m=module()
  with self.assertRaisesRegex(ValueError,'capability_missing'):m.match_catalog([], [{'id':'x','params':'{}'}])
  with self.assertRaisesRegex(ValueError,'capability_mismatch'):m.match_catalog([{'id':'x','params':'{"a":int}'}],[{'id':'x','params':'{"b":int}'}])

 def test_gate_snapshot_does_not_alias_mutable_identity_input(self):
  m=module();identity={'version':'0.2.0-craft.1','versionOutput':'photocraft-cli 0.2.0-craft.1 (dev build)','platform':'darwin-arm64'}
  rows=[{'id':'x','params':'{}','enabled':True}];tools=[{'name':'command_run','inputSchema':{'type':'object'}}]
  class Commands:
   def runtime_rows(self,session):return rows
   def catalog(self):return {'commands':rows}
  class Session:
   def request(self,*args):return {'tools':tools}
  gate=m.Gate(Session(),Commands(),'a'*64,runtime_identity=identity);first=gate.check();identity['version']='0.2.0'
  self.assertEqual(first['runtimeIdentity']['version'],'0.2.0-craft.1')
  with self.assertRaisesRegex(ValueError,'capability_mismatch'):gate.check()

 def test_gateway_missing_initial_capability_has_no_started_step(self):
  import tempfile
  spec=importlib.util.spec_from_file_location('missing_commands',SCRIPTS/'commands.py');commands=importlib.util.module_from_spec(spec);spec.loader.exec_module(commands)
  tools=json.loads((SCRIPTS.parent/'references/native-command-snapshot.json').read_text())['tools']
  class Session:
   def __enter__(self):return self
   def __exit__(self,*a):pass
   def request(self,method,params):
    if method=='tools/list':return {'tools':tools}
    return {'content':[{'type':'text','text':json.dumps([r for r in commands.catalog()['commands'] if r['id']!='layer.renameLayer'])}]}
  with tempfile.TemporaryDirectory() as td:
   result=commands.execute({'schema':'craft-command-plan/v1','operations':[{'command':'layer.renameLayer','params':{'name':'Must not execute'}}]},Path(td)/'output',installer=lambda *a:{'executable':'fixture','binarySha256':'a'*64},session_factory=lambda *a:Session())
   self.assertEqual(result['errorDetails']['code'],'capability_missing');self.assertEqual(result['steps'],[])


class ScopedCapabilityTests(unittest.TestCase):
 def test_unrelated_drift_is_recorded_but_affected_contract_and_enabled_are_checked(self):
  m=module();rows=[{'id':'used','params':'{}','enabled':True},{'id':'other','params':'{}','enabled':True}];tools=[{'name':'command_run','inputSchema':{'type':'object'}},{'name':'other_tool','inputSchema':{'type':'object'}}]
  class Commands:
   def runtime_rows(self,session):return rows
   def catalog(self):return {'commands':rows}
  class Session:
   def request(self,*a):return {'tools':tools}
  gate=m.Gate(Session(),Commands(),'a'*64);initial=gate.check();rows[1]['params']='{"changed":int}';tools[1]['inputSchema']={'type':'array'}
  proof=gate.check_scope(['used'],['command_run'],'used');self.assertNotEqual(proof['actualCommandsSha256'],initial['commandsSha256']);self.assertNotEqual(proof['actualToolsSha256'],initial['toolsSha256'])
  with self.assertRaisesRegex(ValueError,'capability_mismatch'):gate.check_scope(['other'],['command_run'])
  with self.assertRaisesRegex(ValueError,'capability_mismatch'):gate.check_scope(['used'],['other_tool'])
  rows[0]['enabled']=False
  with self.assertRaisesRegex(ValueError,'command_disabled'):gate.check_scope(['used'],['command_run'],'used')
 def test_wrapped_native_command_ids_remain_part_of_affected_scope(self):
  spec=importlib.util.spec_from_file_location('scoped_commands',SCRIPTS/'commands.py');commands=importlib.util.module_from_spec(spec);spec.loader.exec_module(commands)
  self.assertEqual(commands.command_ids({'tool':'command_run','params':{'id':'layer.renameLayer','params':{'name':'X'}}}),['layer.renameLayer'])
  self.assertEqual(commands.command_ids({'tool':'command_batch','params':{'steps':[{'id':'layer.renameLayer','params':{'name':'X'}}]}}),['layer.renameLayer'])
