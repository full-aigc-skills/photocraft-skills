"""持久进度只观察原执行；不能把未知结果或暂存冒充成功交付。"""
import hashlib,importlib.util,json,os,signal,subprocess,sys,tempfile,time,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];SCRIPTS=ROOT/'skills/photocraft-use/scripts'
def load(name):
 spec=importlib.util.spec_from_file_location('progress_test_'+name,SCRIPTS/(name+'.py'));module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def canonical_sha(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
class DurableProgressTests(unittest.TestCase):
 def test_submitted_progress_is_durable_before_unknown_native_reply(self):
  class Journal:
   def __init__(self):self.calls=[]
   def publish(self,state,phase):self.calls.append((phase,json.loads(json.dumps(state['lastAttempt']))))
  journal=Journal();state={'_progress':journal}
  class Session:
   def request(self,*args):
    self_test.assertEqual(journal.calls,[('submitted',{'tool':'doc_inspect','arguments':{},'phase':'submitted'})]);raise RuntimeError('reply lost')
  self_test=self
  with self.assertRaisesRegex(RuntimeError,'reply lost'):load('workflow').call_tool(Session(),'doc_inspect',{},state,[])
 def fixture(self,root):
  output=root/'output';stage=root/'stage';stage.mkdir();plan={'document':{'width':64,'height':64},'operations':[]};identity={'planHash':canonical_sha(plan),'inputHashes':{},'projectRevision':None,'runtimeSha256':'a'*64};state={'operations':[],'recoveryContext':{'schema':'photocraft-recovery-context/v1','plan':plan,'executionIdentity':identity,'bindings':{},'assets':{},'capability':None,'taskBinding':None}};return output,stage,identity,state
 def test_atomic_snapshot_matches_original_guard_and_does_not_change_any_file(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp).resolve();output,stage,identity,state=self.fixture(root);progress=load('progress')
   with load('output_guard').claim(output,identity) as guard:
    journal=progress.Journal(output,stage,guard);journal.publish(state,'prepared');before={str(p):sha(p) for p in root.rglob('*') if p.is_file()};result=progress.read_progress(output,root);self.assertEqual(result['record']['context'],state['recoveryContext']);self.assertEqual(result['record']['sequence'],1);self.assertEqual(result['stage'],str(stage));self.assertFalse(result['replayAllowed']);self.assertEqual(before,{str(p):sha(p) for p in root.rglob('*') if p.is_file()})
    state['lastAttempt']={'tool':'doc_inspect','arguments':{},'phase':'submitted'};journal.publish(state,'submitted');self.assertEqual(progress.read_progress(output,root)['record']['sequence'],2)
   with self.assertRaisesRegex(ValueError,'progress_owner_conflict'):journal.publish(state,'submitted')
 def test_tampered_plan_binding_stage_and_guard_are_refused_readonly(self):
  for field in ['plan','identity','stage','stageIdentity','taskBinding','receipts','phase','guard','ownerRange','stageIdentityShape']:
   with self.subTest(field=field),tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp).resolve();output,stage,identity,state=self.fixture(root);progress=load('progress')
    with load('output_guard').claim(output,identity) as guard:
     journal=progress.Journal(output,stage,guard);journal.publish(state,'prepared');path=progress.record_path(output);value=json.loads(path.read_text())
     if field=='plan':value['context']['plan']['document']['width']=128
     elif field=='identity':value['context']['executionIdentity']['runtimeSha256']='b'*64
     elif field=='stage':value['stage']='../../outside'
     elif field=='stageIdentity':value['stageIdentity']=['0','0']
     elif field=='taskBinding':value['context']['taskBinding']={}
     elif field=='receipts':value['completedOperations']=1
     elif field=='phase':value['phase']='success'
     elif field=='guard':value['targetHash']='f'*64
     elif field=='ownerRange':value['ownerPid']=2**60
     elif field=='stageIdentityShape':value['stageIdentity']=[]
     path.write_text(json.dumps(value));before=sha(path)
     with self.assertRaises(ValueError):progress.read_progress(output,root)
     self.assertEqual(sha(path),before)

@unittest.skipUnless(os.environ.get('PHOTOCRAFT_CHECKPOINT_NATIVE')=='1','requires locked native runtime')
class NativeDurableProgressTests(unittest.TestCase):
 def test_sigkill_after_native_save_retains_submitted_progress_without_failure_record(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp).resolve();output=root/'output';marker=root/'saved';plan={'document':{'width':64,'height':64,'background':'#ffffff'},'operations':[{'command':'type.create','params':{'text':'KEEP','font':'Arial','size':12,'x':8,'y':20},'as':'title'}],'exports':[]};path=root/'plan.json';path.write_text(json.dumps(plan))
   child=subprocess.Popen([sys.executable,'-I','-B',str(ROOT/'tests/fixtures/workflow_progress_pause.py'),str(marker),str(SCRIPTS/'workflow.py'),str(path),'--output',str(output)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
   native_pid=None
   try:
    deadline=time.monotonic()+30
    while not marker.exists():
     if child.poll() is not None or time.monotonic()>deadline:self.fail('save window not reached: '+str(child.communicate(timeout=5)))
     time.sleep(.02)
    native_pid=json.loads(marker.read_text())['nativePid'];os.kill(child.pid,signal.SIGKILL);child.communicate(timeout=10)
    progress=load('progress');snapshot=progress.read_progress(output,root);record=snapshot['record'];stage=Path(snapshot['stage']);self.assertEqual(record['phase'],'submitted');self.assertEqual(record['lastAttempt']['tool'],'doc_save');self.assertFalse(any(row['tool']=='doc_save' for row in record['operations']));self.assertFalse((output/'failure.json').exists());self.assertFalse((stage/'failure.json').exists());self.assertTrue((stage/'project.pcraft').is_file());self.assertEqual(record['context']['plan'],plan);self.assertIn('title',record['context']['bindings']);self.assertFalse(record['replayAllowed']);self.assertEqual(record['context']['executionIdentity']['planHashAlgorithm'],load('plan_identity').ALGORITHM);self.assertEqual(record['context']['executionIdentity']['planHash'],load('plan_identity').sha(plan,load('plan_identity').ALGORITHM))
    before={str(p):sha(p) for p in root.rglob('*') if p.is_file()};again=progress.read_progress(output,root);self.assertEqual(again,snapshot);self.assertEqual(before,{str(p):sha(p) for p in root.rglob('*') if p.is_file()})
    with self.assertRaisesRegex(ValueError,'output_execution_reconciling'):
     with load('output_guard').claim(output,record['context']['executionIdentity']):self.fail('unknown execution replayed')
    if os.environ.get('PHOTOCRAFT_PROGRESS_REPORT'):Path(os.environ['PHOTOCRAFT_PROGRESS_REPORT']).write_text(json.dumps({'schema':'photocraft-durable-progress-native/v1','status':'PASS','recordSha256':snapshot['recordSha256'],'planSha256':record['context']['executionIdentity']['planHash'],'runtimeSha256':record['context']['executionIdentity']['runtimeSha256'],'savedProjectSha256':sha(stage/'project.pcraft'),'phase':record['phase'],'lastAttempt':record['lastAttempt'],'completedOperations':record['completedOperations'],'saveConfirmed':False,'savedNativeExists':True,'failureRecordExists':False,'originalFilesUnchanged':True,'replayRefused':True,'technical':'NOT_RUN','creative':'NOT_RUN','scope':'Actual native save then SIGKILL; read-only progress only, no owned-worker proof or checkpoint recovery acceptance.'},indent=2)+'\n')
   finally:
    if child.poll() is None:child.kill();child.communicate(timeout=10)
    if native_pid:
     try:os.kill(native_pid,signal.SIGTERM)
     except ProcessLookupError:pass
