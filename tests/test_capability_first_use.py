"""真实双后端保存后注入能力回复漂移；不替换二进制或执行未知编辑。"""
import copy,hashlib,importlib.util,json,os,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(path,name):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
@unittest.skipUnless(os.environ.get('CRAFT_CAPABILITY_FIRST_USE')=='1','explicit native+desktop capability opt-in')
class CapabilityFirstUse(unittest.TestCase):
 def test_both_backends_bind_identity_and_stop_drift_before_next_edit(self):
  root=os.environ.get('CRAFT_CAPABILITY_OUTPUT')
  if root:
   path=Path(root).resolve();path.mkdir(parents=True,exist_ok=False);self.run_case(path)
  else:
   with tempfile.TemporaryDirectory(prefix='photo-capability-') as td:self.run_case(Path(td))
 def run_case(self,root):
  skill=Path(os.environ.get('CRAFT_INSTALLED_CAPABILITY_SKILL',ROOT/'skills/photocraft-cli'));scripts=skill/'scripts'
  def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
  def hashes(p):return {str(f.relative_to(p)):sha(f) for f in p.rglob('*') if f.is_file() and '__pycache__' not in str(f)}
  before=hashes(skill);runtime=root/'runtime';records=[]
  cli_lock=json.loads((scripts/'runtime.lock.json').read_text());desktop_lock=json.loads((scripts/'desktop.lock.json').read_text())
  for backend in ['headless','bridge']:
   for fault in ['none','initial-missing','params','tool-schema','missing','unrelated-params','unrelated-tool']:
    output=root/(backend+'-'+fault);commands=load(scripts/'commands.py','actual_commands_'+backend+fault)
    trace=[];state={'saved':False,'faultCount':0};cmd='layer.renameLayer'
    def observe(method,params,result):
     # 原生回复已完成，注入仅改动只读发现回复；原生二进制和客户端资源不改写。
     if method=='tools/call':
      name=params['name'];args=params['arguments']
      if name=='doc_save':state['saved']=True
      if name not in ('commands','commands_list','list_commands'):trace.append({'tool':name,'id':args.get('id'),'path':args.get('path')})
     if (not state['saved'] and fault!='initial-missing') or fault=='none':return result
     if method=='tools/list' and fault in ('tool-schema','unrelated-tool'):
      result=copy.deepcopy(result)
      tool=next(t for t in result['tools'] if t['name']==('doc_close' if fault=='unrelated-tool' else 'command_run'));tool['inputSchema']={**tool['inputSchema'],'description':'deliberate test-only schema drift'};state['faultCount']+=1
     if method=='tools/call' and params['name']==commands.ROUTES[commands.DOMAIN][0] and fault in ('params','missing','initial-missing','unrelated-params'):
      result=copy.deepcopy(result);text=next(c for c in result['content'] if c['type']=='text');rows=json.loads(text['text'])
      if isinstance(rows,dict):rows=rows['commands']
      if fault in ('params','unrelated-params'):
       for row in rows:
        if row['id']==('file.new' if fault=='unrelated-params' else cmd):row['params']='{"changedByFault":int}';state['faultCount']+=1
      else:rows=[row for row in rows if row['id']!=cmd]
      text['text']=json.dumps(rows);state['faultCount']+=1
     return result
    plan={'schema':'craft-command-plan/v1','operations':[{'tool':'doc_new','params':{'width':32,'height':32}},{'command':'layer.new.layer','params':{'name':'Preserved'},'as':'layer'},{'tool':'doc_save','params':{'path':{'$output':'checkpoint.pcraft'}}},{'command':cmd,'params':{'layer':{'$ref':'layer.layer'},'name':'After check'}},{'tool':'doc_save','params':{'path':{'$output':'final.pcraft'}}}]}
    if backend=='headless':
     session_module=load(scripts/'mcp_session.py','real_session');base=session_module.Session
     class Observed(base):
      def request(self,method,params):return observe(method,params,super().request(method,params))
     receipt=commands.execute(plan,output,runtime,session_factory=Observed)
    else:
     desktop=load(scripts/'desktop_session.py','real_desktop');base=desktop.OwnedSession;oldload=desktop.load
     class Observed(base):
      def request(self,method,params):return observe(method,params,super().request(method,params))
     desktop.OwnedSession=Observed;desktop.load=lambda name:commands if name=='commands' else oldload(name)
     receipt=desktop.run(plan,output,runtime)
     lifecycle=json.loads((output/'desktop-session.json').read_text());self.assertTrue(lifecycle['ownedProcessesStopped']);self.assertTrue(lifecycle['listenerOwnedByPID'])
    if fault=='initial-missing':
     self.assertEqual(receipt['result'],'FAIL');self.assertEqual(receipt['errorDetails']['code'],'capability_missing');self.assertEqual(receipt['steps'],[]);self.assertFalse((output/'checkpoint.pcraft').exists());self.assertFalse((output/'success.json').exists());self.assertGreater(state['faultCount'],0);self.assertFalse(any(x['tool'] in ('doc_new','doc_save','command_run') for x in trace));records.append({'backend':backend,'fault':fault,'result':'FAIL','errorCode':'capability_missing','steps':0,'faultCount':state['faultCount'],'laterEditCalls':0,'runtimeSha256':receipt['runtimeSha256'],'receiptSha256':sha(output/'failure.json'),'ownedProcessesStopped':backend=='headless' or lifecycle['ownedProcessesStopped']});continue
    capability=receipt['capabilitySnapshot'];self.assertEqual(capability['runtimeIdentity']['version'],cli_lock['resolvedVersion']);self.assertEqual(capability['runtimeIdentity']['platform'],'darwin-arm64');self.assertEqual(capability['runtimeIdentity']['versionOutput'],cli_lock['artifacts']['darwin-arm64']['versionOutput']);self.assertEqual(capability['binarySha256'],cli_lock['artifacts']['darwin-arm64']['binarySha256']);self.assertEqual(capability['backend'],backend);self.assertTrue(capability['sessionId'])
    self.assertEqual(capability['commandCount'],755 if backend=='headless' else 748)
    if backend=='bridge':self.assertEqual(capability['desktopIdentity'],{'version':desktop_lock['version'],'binarySha256':desktop_lock['binarySha256']})
    else:self.assertIsNone(capability['desktopIdentity'])
    if fault in ('none','unrelated-params','unrelated-tool'):self.assertEqual(receipt['result'],'PASS');self.assertTrue((output/'final.pcraft').is_file());self.assertEqual(len(receipt['steps']),5)
    else:
     self.assertEqual(receipt['result'],'FAIL',receipt);self.assertGreater(state['faultCount'],0);self.assertIn(receipt['errorDetails']['code'],['capability_mismatch','capability_missing']);self.assertEqual(len(receipt['steps']),3);self.assertFalse((output/'final.pcraft').exists());self.assertFalse((output/'success.json').exists());self.assertFalse(any(x.get('id')==cmd for x in trace))
    if fault in ('unrelated-params','unrelated-tool'):
     self.assertGreater(state['faultCount'],0);self.assertTrue(any(check['actualCommandsSha256']!=capability['commandsSha256'] or check['actualToolsSha256']!=capability['toolsSha256'] for check in receipt['capabilityChecks']))
    checkpoint=output/'checkpoint.pcraft';checkpoint_sha=sha(checkpoint)
    bootstrap=load(scripts/'bootstrap.py','actual_bootstrap');installed=bootstrap.install(cli_lock,runtime)
    session_module=load(scripts/'mcp_session.py','reopen_session')
    with session_module.Session([installed['executable'],'mcp','--automation-read-root',str(output),'--automation-write-root',str(output)]) as session:
     commands.parse_reply(session.request('tools/call',{'name':'doc_open','arguments':{'path':'checkpoint.pcraft'}}));native=commands.parse_reply(session.request('tools/call',{'name':'doc_inspect','arguments':{}}));self.assertTrue(any(l['name']=='Preserved' for l in native['layers']));self.assertFalse(any(l['name']=='After check' for l in native['layers']))
    self.assertEqual(sha(checkpoint),checkpoint_sha);records.append({'backend':backend,'fault':fault,'result':receipt['result'],'capabilitySnapshot':capability,'faultCount':state['faultCount'],'checkpointSha256':checkpoint_sha,'checkpointFreshReopenAndUnchanged':True,'laterEditCalls':sum(x.get('id')==cmd for x in trace),'receiptSha256':sha(output/('success.json' if receipt['result']=='PASS' else 'failure.json')),'ownedProcessesStopped':backend=='headless' or lifecycle['ownedProcessesStopped']})
  self.assertEqual(hashes(skill),before)
  proof={'schema':'photocraft-capability-first-use/v1','status':'PASS','platform':'darwin-arm64','cases':records,'skillUnchanged':True,'skillFilesSha256':hashlib.sha256(json.dumps(before,sort_keys=True).encode()).hexdigest(),'driverSha256':sha(Path(__file__)),'artifacts':hashes(root),'scope':'fixed native headless and owned signed desktop, with explicitly injected discovery-reply faults after real save; no claim that native servers spontaneously drifted; full upgrade/rollback, creative and exhaustive commands separate'}
  if os.environ.get('CRAFT_CAPABILITY_REPORT'):Path(os.environ['CRAFT_CAPABILITY_REPORT']).write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n')
