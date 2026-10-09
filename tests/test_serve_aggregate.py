"""批量中的真实保存后失败必须先停止，再允许后续编辑或共享连接。"""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS=Path(__file__).resolve().parents[1]/'skills/photocraft-use/scripts'
def load(name):
 spec=importlib.util.spec_from_file_location('aggregate_test_'+name,SCRIPTS/(name+'.py'));module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

class AggregatePreflight(unittest.TestCase):
 def test_invalid_last_step_prevents_entire_batch_install_and_output(self):
  stream=load('serve_stream');calls=[]
  def forbidden():calls.append('install');raise AssertionError('invalid batch installed')
  message={'id':1,'method':'batch','params':{'steps':[{'method':'doc.new','params':{'width':16,'height':16}},{'method':'doc.save','params':{'path':'never.pcraft'}},{'command':'layer.new.layer','params':{'opacity':'bad'}}]}}
  output=io.StringIO();code=stream.run(['serve'],forbidden,io.StringIO(json.dumps(message)+'\n'),output)
  self.assertEqual(code,1);self.assertEqual(calls,[]);detail=json.loads(output.getvalue())['errorData'];self.assertEqual(detail['outcome'],'not_executed');self.assertEqual(detail['phase'],'validation');self.assertEqual(detail['receipts'],[])

 def test_oversized_outer_batch_rejects_before_decomposition_and_install(self):
  stream=load('serve_stream');calls=[];output=io.StringIO()
  def forbidden():calls.append('install');raise AssertionError('oversized request installed')
  message={'id':1,'method':'batch','params':{'steps':[{'command':'layer.new.layer','params':{'name':'x'*(1<<20)}}]}}
  code=stream.run(['serve'],forbidden,io.StringIO(json.dumps(message)+'\n'),output)
  self.assertEqual(code,1);self.assertEqual(calls,[]);detail=json.loads(output.getvalue())['errorData'];self.assertEqual(detail['outcome'],'not_executed');self.assertEqual(detail['code'],'request_too_large')

@unittest.skipUnless(os.environ.get('CRAFT_SERVE_AGGREGATE_NATIVE')=='1','explicit real native aggregate opt-in')
class NativeAggregate(unittest.TestCase):
 def test_stdio_explicit_continue_cannot_run_edit_after_failed_step(self):self.check('stdio','native-error')
 def test_tcp_explicit_continue_cannot_run_edit_after_failed_step(self):self.check('tcp','native-error')
 def test_stdio_save_reply_fault_stops_inside_batch(self):
  for fault in ['duplicate','nonfinite','semantic','wrong-id','extra-frame','malformed-error','missing-ok']:
   with self.subTest(fault=fault):self.check('stdio',fault)
 def test_tcp_save_reply_fault_stops_inside_shared_batch(self):
  for fault in ['duplicate','nonfinite','semantic','wrong-id','extra-frame','malformed-error','missing-ok']:
   with self.subTest(fault=fault):self.check('tcp',fault)
 def test_stdio_healthy_batch_preserves_results_and_compound_id(self):self.check('stdio',None)
 def test_tcp_healthy_batch_preserves_results_and_compound_id(self):self.check('tcp',None)
 def test_stdio_aggregate_response_budget_prevents_later_edit(self):self.check('stdio','budget')
 def test_tcp_aggregate_response_budget_prevents_later_edit(self):self.check('tcp','budget')
 def check(self,transport,fault):
  runtime=os.environ['CRAFT_RUNTIME_HOME'];cli=SCRIPTS/'cli.py'
  installed=json.loads(subprocess.check_output([os.sys.executable,'-I','-B',str(SCRIPTS/'bootstrap.py'),'--runtime-home',runtime],text=True))
  # Only alter the bytes read after the actual fixed native save; never replace execution.
  stream=load('serve_stream');tcp=load('serve_tcp');records=[];sent=[]
  with tempfile.TemporaryDirectory(prefix='photo-aggregate-') as temporary:
   root=Path(temporary);source=root/'source.pcraft';saved=root/'saved.pcraft'
   created=subprocess.run([os.sys.executable,'-I','-B',str(cli),'--runtime-home',runtime,'--','run','--new={"width":16,"height":16}','--cmd=layer.new.layer','--params={"name":"Source"}','--out',str(source)],capture_output=True,text=True,timeout=30)
   self.assertEqual(created.returncode,0,created.stdout+created.stderr);source_sha=hashlib.sha256(source.read_bytes()).hexdigest()
   original_read=stream.Wire.read_line;original_send=stream.Wire.send
   def send(wire,message):wire.current=message;sent.append(message);return original_send(wire,message)
   def read(wire,deadline):
    raw=original_read(wire,deadline);request=wire.current;reply=json.loads(raw)
    if request['method']=='doc.save' and fault not in {None,'native-error','budget'}:
     if fault=='duplicate':return b'{"ok":true,'+raw[1:]
     if fault=='nonfinite':return b'{"probe":NaN,'+raw[1:]
     if fault=='semantic':reply['result']={'error':'post-save semantic failure'}
     elif fault=='wrong-id':reply['id']='other'
     elif fault=='extra-frame':wire.buffer=json.dumps(reply).encode()+b'\n'+wire.buffer
     elif fault=='malformed-error':reply.pop('result');reply['ok']=False;reply['error']={'bad':'shape'}
     elif fault=='missing-ok':reply.pop('ok')
     return json.dumps(reply).encode()
    return raw
   steps=[{'method':'doc.save','params':{'path':'saved.pcraft'}}]
   if fault=='budget':steps.extend([{'method':'engine.commands'} for _ in range(80)])
   if fault=='native-error':steps.append({'method':'doc.select','params':{'index':99}})
   steps.extend([{'command':'layer.new.layer','params':{'name':'Forbidden' if fault else 'Healthy'}},{'method':'doc.save','params':{'path':'saved.pcraft'}}])
   if fault is None:steps.extend([{'method':'doc.inspect'},{'method':'doc.render','params':{'maxSide':8}}])
   message={'id':{'batch':[True,1]},'method':'batch','params':{'steps':steps,'stopOnError':False}}
   before={'id':'open','method':'doc.open','params':{'path':'source.pcraft'}}
   argv=['serve','--automation-read-root',str(root),'--automation-write-root',str(root)]
   with patch.object(stream.Wire,'send',send),patch.object(stream.Wire,'read_line',read):
    if transport=='stdio':
     output=io.StringIO();code=stream.run(argv,lambda:installed,io.StringIO('\n'.join(json.dumps(m) for m in [before,message,{'id':'later','method':'methods'}])+'\n'),output)
     replies=[json.loads(line) for line in output.getvalue().splitlines()];reply=replies[1]
     self.assertEqual(code,1 if fault else 0,output.getvalue())
    else:
     gateway=tcp.Gateway(argv,lambda:installed);gateway.stream=stream
     try:
      first,keep=gateway.execute(before);self.assertTrue(keep,first);reply,keep=gateway.execute(message)
      self.assertEqual(keep,not bool(fault),reply)
      if fault:
       blocked,keep=gateway.execute({'id':'later','method':'engine.execute','params':{'command':'layer.new.layer','params':{'name':'OtherClient'}}});self.assertFalse(keep);self.assertEqual(blocked['errorData']['code'],'serve_session_quarantined')
     finally:gateway.close()
   self.assertEqual(reply['id'],message['id']);self.assertTrue(saved.is_file())
   saved_sha=hashlib.sha256(saved.read_bytes()).hexdigest()
   reopened=subprocess.run([os.sys.executable,'-I','-B',str(cli),'--runtime-home',runtime,'--','info',str(saved)],capture_output=True,text=True,timeout=30)
   self.assertEqual(reopened.returncode,0,reopened.stdout+reopened.stderr);names=[layer['name'] for layer in json.loads(reopened.stdout)['layers']]
   self.assertIn('Source',names);self.assertEqual(source_sha,hashlib.sha256(source.read_bytes()).hexdigest());self.assertEqual(saved_sha,hashlib.sha256(saved.read_bytes()).hexdigest())
   if fault:
    self.assertNotIn('Forbidden',names);self.assertNotIn('OtherClient',names)
    self.assertFalse(reply['ok']);detail=reply['errorData'];self.assertFalse(detail['replayAllowed']);self.assertFalse(detail['retryable']);self.assertEqual(detail['request'],message)
    if fault=='budget':
     self.assertEqual(detail['code'],'outcome_unknown');self.assertGreater(detail['aggregate']['confirmedSteps'],1);self.assertLess(detail['aggregate']['stepIndex'],81)
    else:
     self.assertEqual(detail['aggregate']['stepIndex'],1 if fault=='native-error' else 0);self.assertEqual(detail['aggregate']['confirmedSteps'],1 if fault=='native-error' else 0)
    self.assertFalse(any(m['method']=='engine.execute' for m in sent));self.assertFalse(any(m.get('id')=='later' for m in sent))
   else:
    self.assertIn('Healthy',names);self.assertTrue(reply['ok']);result=reply['result'];self.assertEqual(result['completed'],5);self.assertEqual(result['failed'],0);self.assertEqual(len(result['results']),5);self.assertEqual(result['results'][0]['result']['path'],'saved.pcraft');self.assertEqual(result['results'][4]['result']['mime'],'image/png')
   records.append({'transport':transport,'fault':fault,'status':'PASS','sourceSha256':source_sha,'savedSha256':saved_sha,'savedReopened':True,'noLaterEdit':bool(fault),'sentMethods':[m['method'] for m in sent]})
  if os.environ.get('CRAFT_SERVE_AGGREGATE_REPORT'):
   p=Path(os.environ['CRAFT_SERVE_AGGREGATE_REPORT']);v=json.loads(p.read_text()) if p.exists() else {'status':'PASS','cases':[]};v['cases']+=records;p.write_text(json.dumps(v,indent=2)+'\n')

if __name__=='__main__':unittest.main()
