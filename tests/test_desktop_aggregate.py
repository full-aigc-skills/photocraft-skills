"""桌面聚合截止时间和真实GUI失败后保全；不以headless替代桌面验收。"""
import importlib.util,json,os,sys,tempfile,time,unittest
from pathlib import Path
SCRIPTS=Path(__file__).resolve().parents[1]/'skills/photocraft-use/scripts'
def load(name):
 spec=importlib.util.spec_from_file_location('desktop_aggregate_'+name,SCRIPTS/(name+'.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
class DesktopDeadline(unittest.TestCase):
 def test_owned_wrapper_applies_remaining_timeout_to_real_stdio_request(self):
  desktop=load('desktop_session');mcp=load('mcp_session')
  server="""import json,sys,time
for line in sys.stdin:
 m=json.loads(line)
 if 'id' not in m:continue
 if m['method']=='delayed':time.sleep(.3)
 print(json.dumps({'jsonrpc':'2.0','id':m['id'],'result':{}}),flush=True)
"""
  with tempfile.TemporaryDirectory() as tmp:
   owned=desktop.OwnedSession([],{},'photocraft',Path(tmp),1)
   owned.session=mcp.Session([sys.executable,'-u','-c',server])
   try:
    owned.timeout=.05;started=time.monotonic()
    with self.assertRaisesRegex(TimeoutError,'outcome_unknown'):owned.request('delayed',{})
    self.assertLess(time.monotonic()-started,.2)
   finally:owned.close()

import hashlib,select,subprocess
from unittest.mock import patch
@unittest.skipUnless(os.environ.get('CRAFT_DESKTOP_AGGREGATE_NATIVE')=='1','explicit signed GUI aggregate opt-in')
class NativeDesktopAggregate(unittest.TestCase):
 def test_healthy_gui_batch_alias_save_reopen_and_notification(self):
  for notifications in [False,True]:
   with self.subTest(notifications=notifications):self.check(None,notifications)
 def test_native_gui_error_stops_explicit_continue(self):self.check('native-error')
 def test_gui_reply_faults_stop_later_edit(self):
  for fault in ['duplicate','nonfinite','semantic','wrong-id','extra-frame','malformed-error','missing-jsonrpc']:
   with self.subTest(fault=fault):self.check(fault)
 def test_gui_response_budget_stops_before_later_edit(self):self.check('budget')
 def test_gui_batch_deadline_reaches_owned_stdio_request(self):self.check('deadline')
 def check(self,fault,notifications=False):
  runtime=os.environ['CRAFT_RUNTIME_HOME'];desktop=load('desktop_session');commands=load('commands');mcp=load('mcp_session');original_load=desktop.load;original_json=mcp.strict_json;original_select=mcp.select.select
  state={'observing':False,'current':None,'injected':False,'wire':None,'owners':[],'batchStarted':None,'deadlineTimeout':None};sent=[];live=[]
  def decode(raw):
   value=original_json(raw);wire=state['wire'];current=state['current'];p=current.get('params') or {};a=p.get('arguments') or {}
   target=p.get('name')=='command_run' and a.get('id')=='layer.new.layer' and (a.get('params') or {}).get('name')=='Preserved'
   if state['observing'] or not target or state['injected']:return value
   if notifications:
    state['injected']=True;wire.buffer+=b'{"jsonrpc":"2.0","method":"notifications/progress","params":{"progressToken":"gui-batch","progress":1}}\n';return value
   if fault in {None,'native-error','budget','deadline'}:return value
   state['injected']=True
   if fault=='duplicate':return original_json(b'{"jsonrpc":"2.0",'+raw[1:])
   if fault=='nonfinite':return original_json(b'{"probe":NaN,'+raw[1:])
   if fault=='semantic':value['result']={'content':[{'type':'text','text':'{"error":"native semantic failure"}'}]}
   elif fault=='wrong-id':value['id']='foreign'
   elif fault=='extra-frame':wire.buffer=json.dumps(value).encode()+b'\n'+wire.buffer
   elif fault=='malformed-error':value.pop('result');value['error']={'code':'bad','message':7}
   elif fault=='missing-jsonrpc':value.pop('jsonrpc')
   return value
  def readiness(read,write,exc,timeout=0):
   current=state['current'] or {};p=current.get('params') or {};a=p.get('arguments') or {}
   target=p.get('name')=='command_run' and (a.get('params') or {}).get('name')=='Preserved'
   if fault=='deadline' and target and not state['observing'] and not state['injected']:
    state['injected']=True;state['deadlineTimeout']=timeout;time.sleep(min(timeout+.01,.3))
    if timeout<=.12:return [],[],[]
    return original_select(read,write,exc,0)
   return original_select(read,write,exc,timeout)
  class Observed(mcp.Session):
   def send(self,message):state['wire']=self;state['current']=message;sent.append(message);return super().send(message)
   def request(self,method,params):
    result=super().request(method,params)
    if fault=='deadline' and method=='tools/call' and params.get('name')=='doc_save':
     # Set the aggregate budget on the public wrapper after the real checkpoint exists.
     state['owners'][0].timeout=.12;state['batchStarted']=time.monotonic()
    return result
   def close(self):
    try:
     if self.process.poll() is None and not state['observing']:
      state['observing']=True;self.buffer=b''
      while original_select([self.process.stdout],[],[],0)[0]:
       if not os.read(self.process.stdout.fileno(),65536):break
      self.timeout=10;live.append(commands.parse_reply(self.request('tools/call',{'name':'doc_inspect','arguments':{}})))
    finally:super().close()
  class Owned(desktop.OwnedSession):
   def __enter__(self):state['owners'].append(self);return super().__enter__()
  with tempfile.TemporaryDirectory(prefix='photo-gui-aggregate-') as tmp:
   root=Path(tmp);source=root/'source.pcraft';out=root/'output'
   created=subprocess.run([sys.executable,'-I','-B',str(SCRIPTS/'cli.py'),'--runtime-home',runtime,'--','run','--new={"width":16,"height":16}','--cmd=layer.new.layer','--params={"name":"Source"}','--out',str(source)],capture_output=True,text=True,timeout=30);self.assertEqual(created.returncode,0,created.stdout+created.stderr);source_sha=hashlib.sha256(source.read_bytes()).hexdigest()
   steps=[{'id':'layer.new.layer','params':{'name':'Preserved'}}]
   if fault=='native-error':steps.append({'id':'layer.select','params':{'layer':999999}})
   if fault=='budget':steps.extend([{'id':'command.list','params':{}} for _ in range(200)])
   steps.append({'id':'layer.new.layer','params':{'name':'Forbidden' if fault else 'Healthy'}})
   plan={'schema':'craft-command-plan/v1','operations':[{'tool':'doc_open','params':{'path':{'$ref':'project.path'}}},{'tool':'doc_save','params':{'path':'checkpoint.pcraft'}},{'tool':'ui_inspect','params':{}},{'tool':'command_batch','params':{'steps':steps,'stop_on_error':False},'as':'batch'},{'tool':'doc_save','params':{'path':'later.pcraft'}}]}
   if fault is None:
    plan['operations'].insert(4,{'command':'layer.renameLayer','params':{'layer':{'$ref':'batch.results.0.result.layer'},'name':'Bound'}})
    plan['operations'] += [{'tool':'doc_open','params':{'path':'later.pcraft'}},{'tool':'doc_inspect','params':{}}]
   with patch.object(mcp,'Session',Observed),patch.object(mcp,'strict_json',decode),patch.object(mcp.select,'select',readiness),patch.object(desktop,'OwnedSession',Owned),patch.object(desktop,'load',side_effect=lambda name:mcp if name=='mcp_session' else original_load(name)):
    receipt=desktop.run(plan,out,runtime_home=runtime,inputs={'project':source})
   expected='PASS' if not fault else ('FAIL' if fault in {'semantic','native-error'} else 'unknown')
   self.assertEqual(receipt['result'],expected,receipt);self.assertEqual(len(live),1);names=[r['name'] for r in live[0]['layers']];self.assertIn('Source',names)
   proof=json.loads((out/'desktop-session.json').read_text());self.assertTrue(proof['ownedProcessesStopped']);self.assertTrue(proof['listenerOwnedByPID']);self.assertEqual(proof['sessionsStarted'],1)
   self.assertIsNotNone(state['wire'].process.poll());self.assertIsNotNone(state['owners'][0].process.poll());self.assertEqual(receipt['steps'][2]['state'],'succeeded')
   checkpoint=out/'checkpoint.pcraft';self.assertTrue(checkpoint.is_file());checkpoint_sha=hashlib.sha256(checkpoint.read_bytes()).hexdigest()
   reopened=subprocess.run([sys.executable,'-I','-B',str(SCRIPTS/'cli.py'),'--runtime-home',runtime,'--','info',str(checkpoint)],capture_output=True,text=True,timeout=30);self.assertEqual(reopened.returncode,0,reopened.stdout+reopened.stderr);self.assertIn('Source',[r['name'] for r in json.loads(reopened.stdout)['layers']]);self.assertEqual(source_sha,hashlib.sha256(source.read_bytes()).hexdigest());self.assertEqual(checkpoint_sha,hashlib.sha256(checkpoint.read_bytes()).hexdigest())
   batch=receipt['steps'][3]
   if fault:
    detail=receipt['errorDetails'];self.assertFalse(detail['retryable']);self.assertFalse(detail['replayAllowed']);self.assertNotIn('Forbidden',names);self.assertFalse((out/'later.pcraft').exists());self.assertFalse((out/'success.json').exists())
    if fault=='budget':self.assertIn('command_batch_response_budget',detail['error']);self.assertGreater(detail['aggregate']['confirmedSteps'],1);self.assertLess(detail['aggregate']['stepIndex'],201)
    elif fault=='deadline':self.assertLessEqual(state['deadlineTimeout'],.12);self.assertEqual(detail['aggregate']['confirmedSteps'],0)
    else:self.assertEqual(detail['aggregate']['confirmedSteps'],1 if fault=='native-error' else 0)
    self.assertFalse(any(((m.get('params') or {}).get('arguments') or {}).get('params',{}).get('name')=='Forbidden' for m in sent if isinstance(((m.get('params') or {}).get('arguments') or {}).get('params',{}),dict)))
   else:
    self.assertEqual(batch['result']['completed'],2);self.assertIn('Bound',names);self.assertIn('Healthy',names);self.assertTrue((out/'later.pcraft').is_file());self.assertEqual(receipt['steps'][-1]['state'],'succeeded')
   if notifications:self.assertTrue(state['injected'])
   target=os.environ.get('CRAFT_DESKTOP_AGGREGATE_REPORT')
   if target:
    path=Path(target);v=json.loads(path.read_text()) if path.exists() else {'schema':'photocraft-desktop-aggregate-native/v1','status':'PASS','cases':[]}
    v['cases'].append({'fault':fault,'notifications':notifications,'status':'PASS','sourceSha256':source_sha,'checkpointSha256':checkpoint_sha,'checkpointReopened':True,'liveLayerNames':names,'ownedDesktopExited':True,'ownedCLIExited':True,'ownedListenerVerified':True,'desktopBinarySha256':proof['desktop']['binarySha256'],'cliBinarySha256':receipt['runtimeSha256'],'uiInspection':receipt['steps'][2]['result'],'confirmedSteps':len(batch.get('substeps',[])),'deadlineTimeout':state['deadlineTimeout'],'scope':'actual signed GUI command plan aggregate; transport fault injection and readonly observation; full public input matrix separate'});path.write_text(json.dumps(v,indent=2)+'\n')

if __name__=='__main__':unittest.main()
