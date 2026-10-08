"""公开CLI编辑必须经逐回复监督；只读入口保留原输出与调用约定。"""
import importlib.util,io,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
SCRIPTS=Path(__file__).resolve().parents[1]/'skills/photocraft-use/scripts'

def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

class PublicSupervision(unittest.TestCase):
 def invoke(self,argv,failure=False):
  cli=load('public_cli_test',SCRIPTS/'cli.py');original=importlib.util.spec_from_file_location;calls=[];stdout=io.StringIO()
  def observe(name,location,*args,**kwargs):
   spec=original(name,location,*args,**kwargs);execute=spec.loader.exec_module
   def hooked(module):
    execute(module)
    if Path(location).name=='bootstrap.py':module.install=lambda *a,**k:{'executable':'verified-native','binarySha256':'a'*64}
    elif Path(location).name=='cli_supervisor.py':
     def supervised(executable,arguments,output,**kwargs):
      calls.append((executable,arguments,kwargs))
      if failure:
       errors=load('public_error_fixture',SCRIPTS/'operation_errors.py');error=errors.OperationError('outcome_unknown: fixture','outcome_unknown');error.receipts=[{'sequence':1}];error.lastAttempt={'sequence':2,'phase':'submitted'};raise error
      output.write('{"command":"layer.new.layer","result":{"layer":2}}\n');return {'result':'PASS'}
     module.execute=supervised
   spec.loader.exec_module=hooked;return spec
  with patch.object(importlib.util,'spec_from_file_location',side_effect=observe),patch.object(sys,'argv',['cli.py','--',*argv]),patch.object(sys,'stdout',stdout),patch.object(cli.subprocess,'run',side_effect=AssertionError('unsupervised editing passthrough')):
   code=cli.main()
  return code,stdout.getvalue(),calls
 def test_run_uses_verified_supervisor_and_keeps_legacy_lines(self):
  code,text,calls=self.invoke(['run','--new={"width":32,"height":32}','--cmd=layer.new.layer','--params={"name":"Title"}','--out=unused.pcraft'])
  self.assertEqual(code,0);self.assertEqual(json.loads(text)['command'],'layer.new.layer');self.assertEqual(len(calls),1);self.assertEqual(calls[0][0],'verified-native');self.assertEqual(calls[0][2]['runtime_version'],json.loads((SCRIPTS/'runtime.lock.json').read_text())['resolvedVersion'])
 def test_unknown_reply_keeps_receipts_request_phase_and_never_replays(self):
  code,text,calls=self.invoke(['run','--new={"width":32,"height":32}','--out=unused.pcraft'],failure=True)
  self.assertEqual(code,1);reply=json.loads(text);self.assertEqual(reply['outcome'],'unknown');self.assertEqual(reply['phase'],'submitted');self.assertFalse(reply['retryable']);self.assertFalse(reply['replayAllowed']);self.assertEqual(reply['receipts'],[{'sequence':1}]);self.assertEqual(reply['lastAttempt']['sequence'],2);self.assertEqual(len(calls),1)


# 原生负例单独启用；公开锁定安装器与二进制始终保持实际身份。
import hashlib,os,subprocess
ROOT=Path(__file__).resolve().parents[1]
@unittest.skipUnless(os.environ.get('CRAFT_PUBLIC_SUPERVISION')=='1','explicit public native supervision opt-in')
class PublicNativeSupervision(unittest.TestCase):
 def test_public_saved_reply_faults_stop_later_edits_and_preserve_original_file(self):
  self.verify('run',['duplicate','nonfinite','semantic','wrong-request','extra-frame'])
 def test_public_final_save_reply_faults_preserve_saved_project(self):
  self.verify('run-final',['save-array','wrong-save-path'])
 def test_public_batch_saved_reply_faults_stop_second_file(self):
  self.verify('batch',['duplicate','semantic','save-array'])
 def test_public_convert_saved_reply_faults_preserve_file(self):
  self.verify('convert',['duplicate','save-array'])
 def test_public_droplet_saved_reply_faults_stop_second_input(self):
  self.verify('droplet',['duplicate','semantic','save-array'])
 def verify(self,kind,faults):
  skill=Path(os.environ.get('CRAFT_PUBLIC_SUPERVISION_SKILL',SCRIPTS.parent));scripts=skill/'scripts';runtime=os.environ.get('CRAFT_RUNTIME_HOME',str(Path.home()/'.local/share/craft-runtimes'));lock=json.loads((scripts/'runtime.lock.json').read_text());rows=[]
  fingerprint=lambda:{str(p.relative_to(skill)):hashlib.sha256(p.read_bytes()).hexdigest() for p in skill.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
  before=fingerprint()
  with tempfile.TemporaryDirectory(prefix='photo-public-supervision-') as temporary:
   root=Path(temporary).resolve()
   def run(*argv):
    result=subprocess.run([sys.executable,'-I','-B',str(scripts/'cli.py'),'--runtime-home',runtime,'--',*argv],capture_output=True,text=True,timeout=60);self.assertEqual(result.returncode,0,result.stdout+result.stderr);return result.stdout
   source=root/'source.pcraft';run('run','--new={"width":32,"height":32}','--cmd=layer.new.layer','--params={"name":"Source"}','--out',str(source));source_sha=hashlib.sha256(source.read_bytes()).hexdigest()
   for fault in faults:
    case=root/fault;case.mkdir();trace=case/'trace.jsonl';saved=case/'saved.pcraft';target=saved;next_target=None
    if kind=='run':
     argv=['run','--new={"width":32,"height":32}','--cmd=layer.new.layer','--params={"name":"Preserved"}','--cmd=file.saveACopy','--params='+json.dumps({'path':str(saved)}),'--cmd=layer.renameLayer','--params={"name":"Never"}'];at=3;last_tool='command_run'
    elif kind=='run-final':argv=['run',str(source),'--cmd=layer.new.layer','--params={"name":"Preserved"}','--out',str(saved)];at=3;last_tool='doc_save'
    elif kind=='convert':argv=['convert',str(source),str(saved)];at=2;last_tool='doc_save'
    elif kind=='batch':
     inputs=case/'inputs';inputs.mkdir();(inputs/'a.pcraft').write_bytes(source.read_bytes());(inputs/'b.pcraft').write_bytes(source.read_bytes());actions=case/'actions.json';actions.write_text('[{"command":"layer.new.layer","params":{"name":"Preserved"}}]');outputs=case/'outputs';argv=['batch','--actions',str(actions),'--in',str(inputs),'--out',str(outputs)];saved=outputs/'a.pcraft';next_target=outputs/'b.pcraft';at=4;last_tool='doc_save'
    else:
     recipe=case/'recipe.pcdroplet';recipe.write_text('{"photocraftDroplet":1,"action":{"name":"Recipe","steps":[["layer.new.layer",{"name":"Preserved"}]]},"options":{"format":"pcraft"}}');outputs=case/'outputs';argv=['droplet',str(recipe),str(source),str(source),'--out',str(outputs)];saved=outputs/'source.pcraft';at=4;last_tool='doc_save'
    result=subprocess.run([sys.executable,'-I','-B',str(ROOT/'tests/fixtures/public_supervision_observer.py'),str(scripts/'cli.py'),str(trace),fault,str(at),'--runtime-home',runtime,'--',*argv],capture_output=True,text=True,timeout=60)
    self.assertEqual(result.returncode,1,result.stdout+result.stderr);reply=json.loads(result.stdout.splitlines()[-1]);self.assertEqual(reply['outcome'],'failed' if fault=='semantic' else 'unknown');self.assertFalse(reply['retryable']);self.assertFalse(reply['replayAllowed']);self.assertEqual(reply['runtimeSha256'],lock['artifacts']['darwin-arm64']['binarySha256']);self.assertEqual(len(reply['receipts']),at-1);self.assertEqual(reply['lastAttempt']['sequence'],at)
    events=[json.loads(line) for line in trace.read_text().splitlines()];native=[x['nativeEvent'] for x in events if 'nativeEvent' in x];confirmations=[x['confirmation'] for x in events if 'confirmation' in x];launches=[x['launch'] for x in events if 'launch' in x]
    self.assertEqual(len(launches),1);self.assertIn('--supervised',launches[0]);self.assertEqual([x['sequence'] for x in native],list(range(1,at+1)));self.assertEqual(native[-1]['tool'],last_tool);self.assertEqual(confirmations,['continue '+str(i)+'\n' for i in range(1,at)])
    self.assertTrue(saved.is_file());saved_sha=hashlib.sha256(saved.read_bytes()).hexdigest();info=json.loads(run('info',str(saved)));self.assertFalse(any(l['name']=='Never' for l in info['layers']));self.assertEqual(hashlib.sha256(saved.read_bytes()).hexdigest(),saved_sha);self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),source_sha)
    if next_target:self.assertFalse(next_target.exists())
    rows.append({'entry':kind,'fault':fault,'status':'PASS','nativeSequences':[x['sequence'] for x in native],'confirmationSequences':list(range(1,at)),'outcome':reply['outcome'],'savedProjectSha256':saved_sha,'freshReadonlyReopen':True,'sourcePreserved':True,'editingLaunches':1,'laterEditingEvents':0})
  self.assertEqual(fingerprint(),before)
  if os.environ.get('CRAFT_PUBLIC_SUPERVISION_REPORT'):
   path=Path(os.environ['CRAFT_PUBLIC_SUPERVISION_REPORT']);old=json.loads(path.read_text()) if path.exists() else {'schema':'photocraft-public-cli-supervision/v1','status':'PASS','runtimeVersion':lock['resolvedVersion'],'runtimeSha256':lock['artifacts']['darwin-arm64']['binarySha256'],'cases':[],'scope':'Actual public CLI and verified native binary; transport observer changes replies after real native execution; streaming and nested aggregates remain separate','closedTaskIds':[]}
   old['cases']+=rows;path.write_text(json.dumps(old,indent=2)+'\n')

if __name__=='__main__':unittest.main()
