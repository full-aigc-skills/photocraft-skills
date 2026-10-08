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
