"""硬中断检查点保留原记录；只有停止证明和固定现场才能成为显式修订来源。"""
import errno,importlib.util,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
SCRIPTS=Path(__file__).resolve().parents[1]/'skills/photocraft-use/scripts'
def load(name):
 spec=importlib.util.spec_from_file_location('interrupted_test_'+name,SCRIPTS/(name+'.py'));module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
class InterruptedCheckpointTests(unittest.TestCase):
 def fixture(self,root):
  progress=load('progress');output=root/'output';stage=root/'stage';stage.mkdir();(stage/'project.pcraft').write_bytes(b'partial native bytes')
  plan={'document':{'width':64,'height':64},'operations':[]};binding={'taskId':'task','taskIdentity':'1'*64,'epoch':1,'workerToken':'owned','sourceSha256':'2'*64}
  identity={'planHash':progress.canonical_sha(plan),'inputHashes':{},'projectRevision':None,'runtimeSha256':'3'*64};context={'schema':'photocraft-recovery-context/v1','plan':plan,'executionIdentity':identity,'bindings':{},'assets':{},'capability':None,'taskBinding':binding}
  guard={'schema':'photocraft-output-execution/v1','ownerPid':os.getpid(),'state':'running','targetHash':progress.target_hash(output),'identity':identity,'replayAllowed':False};progress.guard_path(output).write_text(json.dumps(guard));journal=progress.Journal(output,stage,guard);journal.publish({'recoveryContext':context,'operations':[],'lastAttempt':{'tool':'doc_save','arguments':{'path':'project.pcraft'},'phase':'submitted'}},'submitted')
  launch=root/'launch.json';launch.write_text(json.dumps({'schema':'photocraft-worker-launch/v1',**binding}));receipt=root/'receipt.json';receipt.write_text(json.dumps({'schema':'photocraft-worker-exit/v1',**binding,'launchSha256':load('delivery').sha(launch),'supervisorPid':400001,'workflowPid':os.getpid(),'processGroupGone':True,'stoppedAt':None,'finishedAt':2**52}))
  return output,stage,receipt,launch,progress.read_progress(output,root),context
 def test_new_interrupted_record_is_a_distinct_bound_checkpoint_source(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp).resolve();output,stage,receipt,launch,observed,context=self.fixture(root);checkpoint=root/'checkpoint';checkpoint.mkdir()
   record={'schema':'photocraft-interrupted-checkpoint/v1','status':'interrupted','outcome':'outcome_unknown','stage':'../stage','stageIdentity':observed['record']['stageIdentity'],'progressOutput':str(output),'progressSha256':observed['recordSha256'],'receiptPath':str(receipt),'receiptSha256':load('delivery').sha(receipt),'launchPath':str(launch),'launchSha256':load('delivery').sha(launch),'context':context,'operations':[],'files':{'project.pcraft':{'sha256':load('delivery').sha(stage/'project.pcraft'),'bytes':(stage/'project.pcraft').stat().st_size}},'completedOperations':0,'lastAttempt':observed['record']['lastAttempt'],'replayAllowed':False}
   (checkpoint/'checkpoint.json').write_text(json.dumps(record));contract={'expectedCheckpointSha256':load('delivery').sha(checkpoint/'checkpoint.json'),'expectedCheckpointPlanSha256':context['executionIdentity']['planHash'],'expectedProjectSha256':load('delivery').sha(stage/'project.pcraft')}
   with patch('os.kill',side_effect=ProcessLookupError(errno.ESRCH,'gone')):result=load('checkpoint_source').snapshot(checkpoint,root,contract)
   self.assertEqual(result['stage'],stage);self.assertEqual(result['context'],context);self.assertFalse((stage/'failure.json').exists());self.assertFalse((output/'failure.json').exists())

 def test_capture_is_exclusive_and_preserves_original_files_and_progress(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp).resolve();output,stage,receipt,launch,observed,context=self.fixture(root);module=load('interrupted_checkpoint');checkpoint=root/'checkpoint'
   before={str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()}
   with patch('os.kill',side_effect=ProcessLookupError(errno.ESRCH,'gone')):
    result=module.capture(output,root,checkpoint,observed['recordSha256'],receipt,launch);second=module.capture(output,root,checkpoint,observed['recordSha256'],receipt,launch)
   self.assertEqual(result['recordSha256'],second['recordSha256']);self.assertEqual(result['context'],context)
   for path,data in before.items():self.assertEqual(Path(path).read_bytes(),data)
   self.assertEqual({p.name for p in checkpoint.iterdir()},{'checkpoint.json'})
   (checkpoint/'checkpoint.json').write_text('truncated')
   with patch('os.kill',side_effect=ProcessLookupError(errno.ESRCH,'gone')),self.assertRaises((ValueError,OSError)):
    module.capture(output,root,checkpoint,observed['recordSha256'],receipt,launch)
   self.assertEqual((checkpoint/'checkpoint.json').read_text(),'truncated')
 def test_missing_native_active_foreign_and_changed_proofs_never_create_checkpoint(self):
  for mutation in ['missing','active','foreign','cancelled','launch','changedProgress','symlink','hardlink']:
   with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp).resolve();output,stage,receipt,launch,observed,context=self.fixture(root);checkpoint=root/'checkpoint'
    if mutation=='missing':(stage/'project.pcraft').unlink()
    if mutation in ('foreign','cancelled'):
     value=json.loads(receipt.read_text());value['workerToken' if mutation=='foreign' else 'stoppedAt']='foreign' if mutation=='foreign' else 1;receipt.write_text(json.dumps(value))
    if mutation=='launch':launch.write_text('changed')
    if mutation=='changedProgress':load('progress').record_path(output).write_text('changed')
    if mutation=='symlink':(stage/'foreign').symlink_to(receipt)
    if mutation=='hardlink':os.link(receipt,stage/'foreign')
    effect=None if mutation=='active' else ProcessLookupError(errno.ESRCH,'gone')
    with patch('os.kill',side_effect=effect),self.assertRaises((ValueError,OSError)):
     load('interrupted_checkpoint').capture(output,root,checkpoint,observed['recordSha256'],receipt,launch)
    self.assertFalse(checkpoint.exists());self.assertFalse((output/'failure.json').exists())
 def test_snapshot_rejects_changed_original_files_receipt_and_new_unregistered_files(self):
  for mutation in ['project','extra','receipt','record']:
   with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp).resolve();output,stage,receipt,launch,observed,context=self.fixture(root);checkpoint=root/'checkpoint';module=load('interrupted_checkpoint')
    with patch('os.kill',side_effect=ProcessLookupError(errno.ESRCH,'gone')):module.capture(output,root,checkpoint,observed['recordSha256'],receipt,launch)
    target={'project':stage/'project.pcraft','extra':stage/'new.bin','receipt':receipt,'record':checkpoint/'checkpoint.json'}[mutation];target.write_text('changed')
    with patch('os.kill',side_effect=ProcessLookupError(errno.ESRCH,'gone')),self.assertRaises((ValueError,OSError)):module.read(checkpoint,root)
    self.assertEqual(target.read_text(),'changed')
