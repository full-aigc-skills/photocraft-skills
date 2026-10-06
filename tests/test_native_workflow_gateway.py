import importlib.util,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load():
 path=ROOT/'skills'/ROOT.name.removesuffix('-skills')/'unused'
 path=ROOT/'skills'/(ROOT.name.removesuffix('-skills')+'-use')/'scripts/native_workflow.py'
 s=importlib.util.spec_from_file_location('native',path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class NativeWorkflowTests(unittest.TestCase):
 def test_complete_fixed_catalog_validation(self):
  m=load();rows=m.commands.catalog()['commands']
  for row in rows:m.validate({'command':row['id'],'params':{}})
  for p in [{'command':'invented','params':{}},{'command':rows[0]['id'],'params':{},'executor':'bad'},{'command':rows[0]['id'],'params':{'x':float('inf')}}]:
   with self.assertRaises(ValueError):m.validate(p)
 def test_live_context_and_semantic_reply(self):
  m=load();identifier=m.commands.catalog()['commands'][0]['id']
  class Session:
   def request(self,method,args):
    if args['name']==m.commands.ROUTES[m.commands.DOMAIN][0]:return {'content':[{'type':'text','text':json.dumps([{'id':r['id'],'enabled':r['id']==identifier} for r in m.commands.catalog()['commands']])}]}
    return {'content':[{'type':'text','text':'{"id":17}'}]}
  state={};receipts=[];result=m.execute(Session(),{'command':identifier,'params':{}},state,receipts,ROOT)
  self.assertEqual(result,{'id':17});self.assertEqual(receipts[-1]['nativeCommand'],identifier);self.assertEqual(state['lastAttempt']['phase'],'reply_received')
 def test_disabled_and_unknown_preserved(self):
  m=load();identifier=m.commands.catalog()['commands'][0]['id']
  class Session:
   enabled=False
   def request(self,method,args):
    if args['name']==m.commands.ROUTES[m.commands.DOMAIN][0]:return {'content':[{'type':'text','text':json.dumps([{'id':r['id'],'enabled':self.enabled,'why':'needs_selection'} for r in m.commands.catalog()['commands']])}]}
    return {'content':[{'type':'text','text':'{"id":1,"id":2}'}]}
  s=Session();state={};receipts=[]
  with self.assertRaisesRegex(RuntimeError,'precondition_failed'):m.execute(s,{'command':identifier,'params':{}},state,receipts,ROOT)
  s.enabled=True
  with self.assertRaisesRegex(RuntimeError,'outcome_unknown'):m.execute(s,{'command':identifier,'params':{}},state,receipts,ROOT)
  self.assertEqual(receipts,[]);self.assertEqual(state['lastAttempt']['phase'],'submitted')
