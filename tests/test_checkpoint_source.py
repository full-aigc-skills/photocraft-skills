"""检查点来源必须绑定原失败记录与计划；不把部分工程伪装成成功交付。"""
import hashlib,importlib.util,json,tempfile,unittest,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=ROOT/'skills/photocraft-use/scripts'
def load(name):
 spec=importlib.util.spec_from_file_location('test_'+name,SCRIPTS/(name+'.py'));module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
class CheckpointSourceTests(unittest.TestCase):
 def fixture(self,root):
  output=root/'failed';output.mkdir();stage=root/'stage';stage.mkdir();(stage/'project.pcraft').write_bytes(b'synthetic native fixture')
  plan={'document':{'width':32,'height':32},'operations':[]};plan_sha=hashlib.sha256(json.dumps(plan,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
  context={'taskBinding':None,'schema':'photocraft-recovery-context/v1','plan':plan,'executionIdentity':{'planHash':plan_sha,'inputHashes':{},'projectRevision':None,'runtimeSha256':'9'*64},'bindings':{},'assets':{},'capability':None}
  (stage/'recovery-context.json').write_text(json.dumps(context));(stage/'recovery-operations.json').write_text('[]')
  record={'schema':'craft-failed-stage/v1','status':'failed','outcome':'outcome_unknown','stage':'../stage','files':{p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in stage.iterdir()},'completedOperations':0,'lastAttempt':{'tool':'doc_save','arguments':{'path':'project.pcraft'},'phase':'submitted'},'replayAllowed':False}
  for path in [output/'failure.json',stage/'failure.json']:path.write_text(json.dumps(record))
  contract={'expectedCheckpointSha256':sha(output/'failure.json'),'expectedCheckpointPlanSha256':plan_sha,'expectedProjectSha256':sha(stage/'project.pcraft')}
  return output,stage,record,context,contract
 def test_failure_preserves_verified_execution_context_as_a_hashed_file(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp).resolve();output=root/'failed';context={'schema':'photocraft-recovery-context/v1','plan':{'operations':[]},'bindings':{},'assets':{}};state={'recoveryContext':context}
   with self.assertRaisesRegex(RuntimeError,'unknown'):
    with load('preserved_stage').preserved_stage(output,'.stage-',state) as temporary:
     stage=Path(temporary);(stage/'project.pcraft').write_bytes(b'saved');raise RuntimeError('unknown')
   record=json.loads((output/'failure.json').read_text());self.assertIn('recovery-context.json',record['files']);self.assertEqual(json.loads((stage/'recovery-context.json').read_text()),context)
 def test_task_binding_and_original_registered_assets_cannot_be_forged_by_context(self):
  for mutation in ['task','asset']:
   with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp).resolve();output,stage,record,context,contract=self.fixture(root)
    if mutation=='task':context['taskBinding']={'taskId':'other'}
    else:
     context['plan']['assets']={'image':{'path':'/unused/input.png','sha256':'a'*64}};context['executionIdentity']['planHash']=load('checkpoint_source').canonical_sha(context['plan']);contract['expectedCheckpointPlanSha256']=context['executionIdentity']['planHash']
    (stage/'recovery-context.json').write_text(json.dumps(context));record['files']['recovery-context.json']={'sha256':sha(stage/'recovery-context.json'),'bytes':(stage/'recovery-context.json').stat().st_size}
    for path in [output/'failure.json',stage/'failure.json']:path.write_text(json.dumps(record))
    contract['expectedCheckpointSha256']=sha(output/'failure.json')
    with self.assertRaises(ValueError):load('checkpoint_source').snapshot(output,root,contract)
 def test_bound_snapshot_returns_partial_source_and_never_creates_manifest(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp).resolve();output,stage,record,context,contract=self.fixture(root);result=load('checkpoint_source').snapshot(output,root,contract)
   self.assertEqual(result['stage'],stage);self.assertEqual(result['context'],context);self.assertEqual(result['recordSha256'],contract['expectedCheckpointSha256']);self.assertFalse((stage/'manifest.json').exists())
 def test_wrong_binding_changed_files_missing_context_and_escaping_stage_are_refused(self):
  for mutation in ['record','plan','project','changed','missingContext','escape','runtime','receipts']:
   with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp).resolve();output,stage,record,context,contract=self.fixture(root)
    if mutation in ['record','plan','project']:contract[{'record':'expectedCheckpointSha256','plan':'expectedCheckpointPlanSha256','project':'expectedProjectSha256'}[mutation]]='a'*64
    if mutation=='changed':(stage/'project.pcraft').write_bytes(b'new external changes')
    if mutation=='missingContext':(stage/'recovery-context.json').unlink()
    if mutation=='escape':record['stage']='../../outside'
    if mutation=='runtime':context['executionIdentity']['runtimeSha256']='a'*64;(stage/'recovery-context.json').write_text(json.dumps(context));record['files']['recovery-context.json']={'sha256':sha(stage/'recovery-context.json'),'bytes':(stage/'recovery-context.json').stat().st_size}
    if mutation=='receipts':record['completedOperations']=1
    if mutation in ['escape','runtime','receipts']:
     for path in [output/'failure.json',stage/'failure.json']:path.write_text(json.dumps(record))
     contract['expectedCheckpointSha256']=sha(output/'failure.json')
    with self.assertRaises((ValueError,OSError)):load('checkpoint_source').snapshot(output,root,contract,runtime_sha256='9'*64)

@unittest.skipUnless(os.environ.get('PHOTOCRAFT_CHECKPOINT_NATIVE')=='1','requires locked native runtime')
class NativeCheckpointSourceTests(unittest.TestCase):
 def test_saved_unknown_reply_forks_without_replaying_original_operations(self):
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary).resolve();output=root/'failed';plan={'document':{'width':64,'height':64,'background':'#ffffff'},'operations':[{'command':'type.create','params':{'text':'ORIGINAL','font':'Arial','size':10,'x':4,'y':20},'as':'title'}],'exports':[]};path=root/'plan.json';path.write_text(json.dumps(plan))
   runtime=os.environ.get('CRAFT_RUNTIME_HOME',str(Path.home()/'.local/share/craft-runtimes'))
   args=[sys.executable,'-I','-B',str(ROOT/'tests/fixtures/workflow_protocol_injection.py'),str(ROOT/'tests/fixtures/protocol_proxy.py'),'malformed',str(root/'saves.jsonl'),str(root/'capture.pcraft'),str(root/'reply.json'),str(SCRIPTS/'workflow.py'),str(path),'--output',str(output),'--runtime-home',runtime]
   original=subprocess.run(args,capture_output=True,text=True,timeout=90);self.assertEqual(original.returncode,1,original.stdout+original.stderr);self.assertIn('outcome_unknown',original.stdout)
   record=json.loads((output/'failure.json').read_text());stage=(output/record['stage']).resolve();context=json.loads((stage/'recovery-context.json').read_text());before={str(p.relative_to(root)):sha(p) for p in [*stage.rglob('*'),*output.rglob('*')] if p.is_file()}
   title=context['bindings']['title']['layer'];revision={'operations':[{'command':'type.edit','params':{'layer':{'$ref':'title.layer'},'text':'RECOVERED'}}],'exports':[{'format':'png'}],'expectedCheckpointSha256':sha(output/'failure.json'),'expectedCheckpointPlanSha256':context['executionIdentity']['planHash'],'expectedProjectSha256':sha(stage/'project.pcraft'),'preserveObjects':{str(title):['text.text','bounds']}}
   revision_path=root/'revision.json';revision_path.write_text(json.dumps(revision));new_output=root/'revision'
   result=subprocess.run([sys.executable,'-I','-B',str(SCRIPTS/'workflow.py'),str(revision_path),'--checkpoint',str(output),'--write-root',str(root),'--output',str(new_output),'--runtime-home',runtime],capture_output=True,text=True,timeout=90);self.assertEqual(result.returncode,0,result.stdout+result.stderr)
   manifest=json.loads(result.stdout);self.assertEqual(manifest['sourceProjectSha256'],revision['expectedProjectSha256']);native=json.loads((new_output/'native.json').read_text());layers=load('domain_assertions').index(native);self.assertEqual(layers[str(title)]['text']['text'],'RECOVERED');self.assertEqual(sum(layer['kind']=='Type' for layer in layers.values()),1)
   self.assertEqual(before,{str(p.relative_to(root)):sha(p) for p in [*stage.rglob('*'),*output.rglob('*')] if p.is_file()});self.assertFalse((stage/'manifest.json').exists());self.assertFalse((output/'manifest.json').exists());self.assertEqual((root/'saves.jsonl').read_text().count('saveSucceeded'),1)
   checkpoint_origin=json.loads((new_output/'checkpoint-origin.json').read_text());self.assertEqual(checkpoint_origin['recordSha256'],revision['expectedCheckpointSha256']);self.assertIn('checkpoint-origin.json',manifest['files'])
   if os.environ.get('PHOTOCRAFT_CHECKPOINT_REPORT'):Path(os.environ['PHOTOCRAFT_CHECKPOINT_REPORT']).write_text(json.dumps({'schema':'photocraft-checkpoint-fork-native/v1','status':'PASS','sourceRecordSha256':revision['expectedCheckpointSha256'],'sourcePlanSha256':revision['expectedCheckpointPlanSha256'],'sourceProjectSha256':revision['expectedProjectSha256'],'newProjectSha256':manifest['files']['project.pcraft'],'originalSaveCount':1,'originalFilesUnchanged':True,'typeLayerCount':1,'newText':'RECOVERED','creative':'NOT_RUN','scope':'candidate standalone fork only; harness process proof and fixed publication remain open'},indent=2)+'\n')
