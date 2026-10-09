"""MCP与命令计划的聚合中间失败不得执行后续编辑；真实会话观察。"""
import hashlib,importlib.util,io,json,os,select,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
SCRIPTS=Path(__file__).resolve().parents[1]/'skills/photocraft-use/scripts'
def load(name):
 spec=importlib.util.spec_from_file_location('mcp_aggregate_'+name,SCRIPTS/(name+'.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
class BatchPreflight(unittest.TestCase):
 def test_native_step_limit_refused_before_install_or_output(self):
  commands=load('commands');stream=load('mcp_stream');arguments={'steps':[{'id':'layer.new.layer','params':{}}]*257}
  message={'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'command_batch','arguments':arguments}}
  out=io.StringIO();calls=[]
  def forbidden():calls.append('install');raise AssertionError('oversized batch installed')
  with self.assertRaisesRegex(ValueError,'invalid_batch_steps'):stream.preflight(json.dumps(message))
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'output'
   with self.assertRaisesRegex(ValueError,'invalid_batch_steps'):commands.execute({'schema':'craft-command-plan/v1','operations':[{'tool':'command_batch','params':arguments}]},path,installer=forbidden)
   self.assertFalse(path.exists());self.assertEqual(calls,[])

@unittest.skipUnless(os.environ.get('CRAFT_MCP_AGGREGATE_NATIVE')=='1','explicit native MCP aggregate opt-in')
class NativeMCPAggregate(unittest.TestCase):
 def test_stream_native_error_stops_inside_explicit_continue_batch(self):self.check('stream','native-error')
 def test_plan_native_error_stops_inside_explicit_continue_batch(self):self.check('plan','native-error')
 def test_stream_reply_faults_stop_inside_batch(self):
  for fault in ['duplicate','nonfinite','semantic','wrong-id','extra-frame','malformed-error','missing-jsonrpc']:
   with self.subTest(fault=fault):self.check('stream',fault)
 def test_plan_reply_faults_stop_inside_batch(self):
  for fault in ['duplicate','nonfinite','semantic','wrong-id','extra-frame','malformed-error','missing-jsonrpc']:
   with self.subTest(fault=fault):self.check('plan',fault)
 def test_stream_healthy_batch_preserves_native_results(self):self.check('stream',None)
 def test_plan_healthy_batch_preserves_native_results(self):self.check('plan',None)
 def test_plan_legal_pending_notification_does_not_block_success(self):self.check('plan',None,notifications=True)
 def test_stream_response_budget_stops_before_next_edit(self):self.check('stream','budget')
 def test_plan_response_budget_stops_before_next_edit(self):self.check('plan','budget')
 def check(self,entry,fault,notifications=False):
  runtime=os.environ['CRAFT_RUNTIME_HOME'];cli=SCRIPTS/'cli.py';installed=json.loads(subprocess.check_output([os.sys.executable,'-I','-B',str(SCRIPTS/'bootstrap.py'),'--runtime-home',runtime],text=True))
  commands=load('commands');stream=load('mcp_stream');session=load('mcp_session');sent=[];live=[];injected=[];state={'observing':False,'current':None,'wire':None}
  def fault_reply(raw,wire,current,original):
   value=original(raw)
   if notifications and not state['observing'] and not injected and isinstance(value,dict) and 'result' in value and ((current.get('params') or {}).get('name')=='command_run'):
    injected.append(True);wire.buffer+=b'{"jsonrpc":"2.0","method":"notifications/progress","params":{"progressToken":"batch","progress":1}}\n'
   if state['observing'] or fault in {None,'native-error','budget'} or injected:return value
   p=current.get('params') or {};a=p.get('arguments') or {}
   if p.get('name')!='command_run' or a.get('id')!='layer.new.layer' or (a.get('params') or {}).get('name')!='Preserved':return value
   injected.append(True)
   if fault=='duplicate':return original(b'{"jsonrpc":"2.0",'+raw[1:])
   if fault=='nonfinite':return original(b'{"probe":NaN,'+raw[1:])
   if fault=='semantic':value['result']={'content':[{'type':'text','text':'{"error":"native semantic failure"}'}]}
   elif fault=='wrong-id':value['id']='unrelated'
   elif fault=='extra-frame':wire.buffer=json.dumps(value).encode()+b'\n'+wire.buffer
   elif fault=='malformed-error':value.pop('result');value['error']={'code':'bad','message':7}
   elif fault=='missing-jsonrpc':value.pop('jsonrpc')
   return value
  with tempfile.TemporaryDirectory(prefix='photo-mcp-aggregate-') as tmp:
   root=Path(tmp);source=root/'source.pcraft';output=root/'output'
   created=subprocess.run([os.sys.executable,'-I','-B',str(cli),'--runtime-home',runtime,'--','run','--new={"width":16,"height":16}','--cmd=layer.new.layer','--params={"name":"Source"}','--out',str(source)],capture_output=True,text=True,timeout=30);self.assertEqual(created.returncode,0,created.stdout+created.stderr);source_sha=hashlib.sha256(source.read_bytes()).hexdigest()
   steps=[{'id':'layer.new.layer','params':{'name':'Preserved'}}]
   if fault=='native-error':steps.append({'id':'layer.select','params':{'layer':999999}})
   if fault=='budget':steps.extend([{'id':'command.list','params':{}} for _ in range(80)])
   steps.append({'id':'layer.new.layer','params':{'name':'Forbidden' if fault else 'Healthy'}})
   args={'steps':steps,'stop_on_error':False}
   def observe_native(wire,send,receive):
    # Read-only live inspection is test observation; no edit/save/replay is sent here.
    state['observing']=True;wire.buffer=b''
    while select.select([wire.process.stdout],[],[],0)[0]:
     if not os.read(wire.process.stdout.fileno(),65536):break
    message={'jsonrpc':'2.0','id':'observer','method':'tools/call','params':{'name':'doc_inspect','arguments':{}}}
    send(message);reply=receive(message);live.append(commands.parse_reply(reply['result']))
   if entry=='stream':
    output.mkdir();(output/'source.pcraft').write_bytes(source.read_bytes());original_send=stream.Wire.send;original_read=stream.Wire.read_line;original_close=stream.Wire.close
    def send(wire,message):state['wire']=wire;state['current']=message;sent.append(message);return original_send(wire,message)
    # Strict JSON faults must be injected as bytes, before the production parser.
    def read(wire,deadline):
     raw=original_read(wire,deadline);current=state['current'];p=current.get('params') or {};a=p.get('arguments') or {}
     if not state['observing'] and not injected and fault in {'duplicate','nonfinite'} and p.get('name')=='command_run' and a.get('id')=='layer.new.layer' and (a.get('params') or {}).get('name')=='Preserved':
      injected.append(True);return (b'{"jsonrpc":"2.0",' if fault=='duplicate' else b'{"probe":NaN,')+raw[1:]
     return json.dumps(fault_reply(raw,wire,current,json.loads)).encode()
    def close(wire):
     try:observe_native(wire,lambda m:original_send(wire,m),lambda m:wire.receive(m,io.StringIO()))
     finally:original_close(wire)
    messages=[{'jsonrpc':'2.0','id':'init','method':'initialize','params':{'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'aggregate','version':'1'}}},{'jsonrpc':'2.0','method':'notifications/initialized'}]
    for identifier,name,arguments in [('open','doc_open',{'path':'source.pcraft'}),('checkpoint','doc_save',{'path':'checkpoint.pcraft'}),('batch','command_batch',args),('later','doc_save',{'path':'later.pcraft'})]:messages.append({'jsonrpc':'2.0','id':identifier,'method':'tools/call','params':{'name':name,'arguments':arguments}})
    out=io.StringIO()
    with patch.object(stream.Wire,'send',send),patch.object(stream.Wire,'read_line',read),patch.object(stream.Wire,'close',close):code=stream.run(['mcp','--automation-read-root',str(output),'--automation-write-root',str(output)],lambda:installed,io.StringIO('\n'.join(json.dumps(m) for m in messages)+'\n'),out)
    replies=[json.loads(line) for line in out.getvalue().splitlines()];self.assertEqual(code,1 if fault else 0,out.getvalue());reply=next((r for r in replies if r.get('id')=='batch'),replies[-1]);detail=reply.get('error',{}).get('data')
    result=commands.parse_reply(reply['result']) if not fault else None
   else:
    original_strict=session.strict_json
    class Observed(session.Session):
     def send(self,message):state['wire']=self;state['current']=message;sent.append(message);return super().send(message)
     def close(self):
      try:
       if self.process.poll() is None:
        self.buffer=b'';state['observing']=True
        while select.select([self.process.stdout],[],[],0)[0]:
         if not os.read(self.process.stdout.fileno(),65536):break
        live.append(commands.parse_reply(self.request('tools/call',{'name':'doc_inspect','arguments':{}})))
      finally:super().close()
    def strict(raw):return fault_reply(raw,state['wire'],state['current'],original_strict)
    plan={'schema':'craft-command-plan/v1','operations':[{'tool':'doc_open','params':{'path':{'$ref':'project.path'}}},{'tool':'doc_save','params':{'path':'checkpoint.pcraft'}},{'tool':'command_batch','params':args,'as':'batch'},{'tool':'doc_save','params':{'path':'later.pcraft'}}]}
    if fault is None:plan['operations'].insert(3,{'command':'layer.renameLayer','params':{'layer':{'$ref':'batch.results.0.result.layer'},'name':'Bound'}})
    with patch.object(session,'strict_json',strict):receipt=commands.execute(plan,output,runtime_home=runtime,inputs={'project':source},session_factory=lambda argv:Observed(argv,timeout=120))
    self.assertEqual(receipt['result'],'PASS' if not fault else ('FAIL' if fault in {'semantic','native-error'} else 'unknown'),receipt);detail=receipt.get('errorDetails');result=receipt['steps'][2].get('result')
   self.assertEqual(len(live),1);names=[r['name'] for r in live[0]['layers']];self.assertIn('Source',names)
   checkpoint=output/'checkpoint.pcraft';self.assertTrue(checkpoint.is_file());checkpoint_sha=hashlib.sha256(checkpoint.read_bytes()).hexdigest()
   reopened=subprocess.run([os.sys.executable,'-I','-B',str(cli),'--runtime-home',runtime,'--','info',str(checkpoint)],capture_output=True,text=True,timeout=30);self.assertEqual(reopened.returncode,0,reopened.stdout+reopened.stderr);self.assertIn('Source',[r['name'] for r in json.loads(reopened.stdout)['layers']]);self.assertEqual(source_sha,hashlib.sha256(source.read_bytes()).hexdigest());self.assertEqual(checkpoint_sha,hashlib.sha256(checkpoint.read_bytes()).hexdigest())
   if fault:
    self.assertNotIn('Forbidden',names);self.assertFalse((output/'later.pcraft').exists());self.assertFalse(detail['retryable']);self.assertFalse(detail['replayAllowed']);self.assertEqual(detail['phase'],'reply_received')
    if fault=='budget':
     self.assertEqual(detail['code'],'outcome_unknown');self.assertIn('command_batch_response_budget',detail['error'])
     self.assertGreater(detail['aggregate']['confirmedSteps'],1);self.assertLess(detail['aggregate']['stepIndex'],81)
    else:self.assertEqual(detail['aggregate']['confirmedSteps'],1 if fault=='native-error' else 0)
    self.assertFalse(any((m.get('params') or {}).get('name')=='command_batch' for m in sent));self.assertFalse(any(((m.get('params') or {}).get('arguments') or {}).get('params',{}).get('name')=='Forbidden' for m in sent if isinstance(((m.get('params') or {}).get('arguments') or {}).get('params',{}),dict)))
   else:self.assertIn('Healthy',names);self.assertEqual(result['completed'],2);self.assertEqual(result['failed'],0);self.assertEqual(len(result['results']),2);self.assertTrue((output/'later.pcraft').is_file())
   if entry=='plan' and fault is None:self.assertIn('Bound',names)
   if notifications:self.assertTrue(injected)
   self.assertIsNotNone(state['wire'].process.poll())
   p=os.environ.get('CRAFT_MCP_AGGREGATE_REPORT')
   if p:
    path=Path(p);v=json.loads(path.read_text()) if path.exists() else {'status':'PASS','cases':[]};v['cases'].append({'entry':entry,'fault':fault,'notifications':notifications,'status':'PASS','sourceSha256':source_sha,'checkpointSha256':checkpoint_sha,'checkpointReopened':True,'liveLayerNames':names,'noLaterEdit':bool(fault),'ownedProcessExited':state['wire'].process.poll() is not None});path.write_text(json.dumps(v,indent=2)+'\n')
if __name__=='__main__':unittest.main()
