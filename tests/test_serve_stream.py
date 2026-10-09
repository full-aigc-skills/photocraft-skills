"""公开serve入口必须在安装前拒绝无效首帧，保存后异常不得触发后续编辑。"""
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

SCRIPTS=Path(__file__).resolve().parents[1]/'skills/photocraft-use/scripts'
def load(name,scripts=None):
 spec=importlib.util.spec_from_file_location('serve_test_'+name,(scripts or SCRIPTS)/(name+'.py'))
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

class PublicServePreflight(unittest.TestCase):
 def test_invalid_first_request_never_installs_or_launches(self):
  for scripts in sorted(SCRIPTS.parents[1].glob('*/scripts')):
   for raw in ['{"id":1,"id":2,"method":"doc.new"}\n',json.dumps({'id':1,'method':'engine.execute','params':{'command':'layer.new.layer','params':{'opacity':'bad'}}})+'\n']:
    with self.subTest(skill=scripts.parent.name,raw=raw):
     cli=load('cli',scripts);original=importlib.util.spec_from_file_location;calls=[]
     def observe(name,path,*args,**kwargs):
      spec=original(name,path,*args,**kwargs);execute=spec.loader.exec_module
      def hooked(module):
       execute(module)
       if Path(path).name=='bootstrap.py':
        def forbidden(*args,**kwargs):calls.append('install');raise AssertionError('invalid serve installed runtime')
        module.install=forbidden
      spec.loader.exec_module=hooked;return spec
     output=io.StringIO()
     with patch.object(sys,'argv',['cli.py','--','serve']),patch.object(sys,'stdin',io.StringIO(raw)),patch.object(sys,'stdout',output),patch.object(importlib.util,'spec_from_file_location',side_effect=observe):code=cli.main()
     self.assertEqual(code,1);self.assertEqual(calls,[]);reply=json.loads(output.getvalue());self.assertFalse(reply['ok']);self.assertEqual(reply['errorData']['outcome'],'not_executed')


class ServePathContract(unittest.TestCase):
 def test_native_rejected_paths_never_reach_installer(self):
  stream=load('serve_stream')
  for path in ['', '/absolute', '../escape', 'a/../escape', 'a\\b', 'C:/escape', 'a//b', './a', 'name:stream', 'NUL', 'con.txt', 'folder/COM1.log', 'folder/end.', 'folder/end ']:
   for method in ['doc.open','doc.save','doc.render']:
    calls=[];output=io.StringIO()
    def forbidden():calls.append('install');raise AssertionError('invalid path installed runtime')
    with self.subTest(path=path,method=method):
     code=stream.run(['serve'],forbidden,io.StringIO(json.dumps({'id':1,'method':method,'params':{'path':path}})+'\n'),output)
     self.assertEqual(code,1);self.assertEqual(calls,[]);detail=json.loads(output.getvalue())['errorData'];self.assertEqual(detail['outcome'],'not_executed');self.assertEqual(detail['fieldPath'],'$.params.path')

class ServeContract(unittest.TestCase):
 def test_static_methods_parameters_and_batch_steps_reject_before_side_effects(self):
  stream=load('serve_stream')
  for message in [{'method':'missing'},{'method':'doc.render','params':{'maxSide':-1}},{'method':'doc.select','params':{'index':True}},{'method':'doc.save','params':{'quality':1.5}},{'method':'batch','params':{'steps':[{'command':'layer.new.layer','params':{'opacity':'bad'}}]}},{'method':'batch','params':{'steps':[{'method':'batch','params':{'steps':[]}}]}},{'method':'session.list','params':{'unknown':True}},{'method':'doc.new','params':[]},{'method':'doc.new','unknown':1}]:
   with self.subTest(message=message),self.assertRaises(ValueError):stream.preflight(json.dumps(message))
 def test_identity_preserves_native_json_id_types(self):
  stream=load('serve_stream')
  for left,right,expected in [(True,1,False),(1,1.0,False),({'a':[True]},{'a':[1]},False),({'a':[1,None]},{'a':[1,None]},True),(None,None,True)]:self.assertEqual(stream.same_id(left,right),expected)
 def test_inner_error_and_invalid_render_are_not_success(self):
  stream=load('serve_stream')
  for message,result in [({'method':'engine.execute'},{'error':'native failure'}),({'method':'doc.render'},{'mime':'image/png','base64':'bad'}),({'method':'doc.save'},{'path':'other.pcraft'}),({'method':'session.list'},{}),({'method':'doc.render','params':{'path':'out.png'}},{'path':'other.png','bytes':1})]:
   if message['method']=='doc.save':message['params']={'path':'wanted.pcraft'}
   with self.subTest(message=message),self.assertRaises(RuntimeError):stream.validate_reply(message,{'result':result})

import hashlib
import subprocess
import tempfile
@unittest.skipUnless(os.environ.get('CRAFT_SERVE_STREAM_NATIVE')=='1','explicit real native serve stream opt-in')
class NativeServeStream(unittest.TestCase):
 def test_actual_saved_files_survive_reply_fault_and_no_next_edit(self):
  self.verify(['duplicate','nonfinite','semantic','wrong-id','extra-frame','malformed-error','missing-ok'])
 def test_actual_healthy_native_protocol_ids_render_and_nullable_parameters(self):
  self.verify([None])
 def verify(self,faults):
  cli=load('cli');original=importlib.util.spec_from_file_location;runtime=os.environ['CRAFT_RUNTIME_HOME'];records=[]
  with tempfile.TemporaryDirectory(prefix='photo-serve-stream-') as temporary:
   root=Path(temporary);source=root/'original.pcraft'
   created=subprocess.run([sys.executable,'-I','-B',str(SCRIPTS/'cli.py'),'--runtime-home',runtime,'--','run','--new={"width":32,"height":32}','--cmd=layer.new.layer','--params={"name":"Source"}','--out',str(source)],capture_output=True,text=True,timeout=30)
   self.assertEqual(created.returncode,0,created.stdout+created.stderr);original_sha=hashlib.sha256(source.read_bytes()).hexdigest()
   for fault in faults:
    saved=root/((fault or 'healthy')+'.pcraft');sent=[];seen=[]
    def observe(name,path,*args,**kwargs):
     spec=original(name,path,*args,**kwargs);execute=spec.loader.exec_module
     def hooked(module):
      execute(module)
      if Path(path).name=='serve_stream.py':
       read_line=module.Wire.read_line;send=module.Wire.send
       def send_message(wire,message):sent.append(message);return send(wire,message)
       def read(wire,deadline):
        raw=read_line(wire,deadline);reply=json.loads(raw);seen.append(reply.get('id'))
        if reply.get('id')==4 and fault:
         if fault=='duplicate':return b'{"ok":true,'+raw[1:]
         if fault=='nonfinite':return b'{"probe":NaN,'+raw[1:]
         if fault=='semantic':reply['result']={'error':'injected semantic failure'}
         elif fault=='wrong-id':reply['id']='other'
         elif fault=='extra-frame':wire.buffer=json.dumps(reply).encode()+b'\n'+wire.buffer
         elif fault=='malformed-error':reply.pop('result');reply['ok']=False;reply['error']={'bad':'shape'}
         elif fault=='missing-ok':reply.pop('ok')
         return json.dumps(reply).encode()
        return raw
       module.Wire.send=send_message;module.Wire.read_line=read
     spec.loader.exec_module=hooked;return spec
    messages=[{'id':2,'method':'doc.open','params':{'path':source.name}},{'id':3,'method':'engine.execute','params':{'command':'layer.new.layer','params':{'name':'Preserved'}}},{'id':4,'method':'doc.save','params':{'path':saved.name}},{'id':5,'method':'engine.execute','params':{'command':'layer.renameLayer','params':{'name':'Never'}}}]
    if fault is None:messages.extend([{'id':{'image':[1,True]},'method':'doc.render','params':{'maxSide':16}},{'id':None,'method':'methods','params':None},{'method':'session.list','params':None},{'id':'render-file','method':'doc.render','params':{'path':'preview.png','maxSide':16}},{'id':'new','method':'doc.new','params':{'width':8,'height':8,'resolution':72}}])
    output=io.StringIO()
    with patch.object(sys,'argv',['cli.py','--runtime-home',runtime,'--','serve','--automation-read-root',str(root),'--automation-write-root',str(root)]),patch.object(sys,'stdin',io.StringIO(''.join(json.dumps(m)+'\n' for m in messages))),patch.object(sys,'stdout',output),patch.object(importlib.util,'spec_from_file_location',side_effect=observe):code=cli.main()
    replies=[json.loads(line) for line in output.getvalue().splitlines()]
    self.assertEqual(code,1 if fault else 0,output.getvalue());self.assertEqual([m.get('id') for m in sent],[2,3,4]+([] if fault else [5,{'image':[1,True]},None,None,'render-file','new']))
    if fault:
     detail=replies[-1]['errorData'];self.assertEqual(detail['outcome'],'failed' if fault=='semantic' else 'unknown');self.assertEqual(detail['phase'],'reply_received');self.assertFalse(detail['retryable']);self.assertFalse(detail['replayAllowed']);self.assertEqual(detail['request']['id'],4);self.assertEqual(len(detail['receipts']),2)
    else:
     self.assertEqual(replies[4]['id'],{'image':[1,True]});self.assertEqual(replies[4]['result']['mime'],'image/png');self.assertTrue((root/'preview.png').is_file());self.assertEqual(len(replies),len(messages))
    self.assertTrue(saved.is_file());saved_sha=hashlib.sha256(saved.read_bytes()).hexdigest();reopened=subprocess.run([sys.executable,'-I','-B',str(SCRIPTS/'cli.py'),'--runtime-home',runtime,'--','info',str(saved)],capture_output=True,text=True,timeout=30);self.assertEqual(reopened.returncode,0,reopened.stdout+reopened.stderr);layers=json.loads(reopened.stdout)['layers'];self.assertTrue(any(layer['name']=='Preserved' for layer in layers));self.assertFalse(any(layer['name']=='Never' for layer in layers));self.assertEqual(hashlib.sha256(saved.read_bytes()).hexdigest(),saved_sha);self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),original_sha)
    records.append({'fault':fault,'status':'PASS','sentIds':[m.get('id') for m in sent],'observedReplyIds':seen,'sourcePreserved':True,'savedReopened':True,'savedSha256':saved_sha})
  if os.environ.get('CRAFT_SERVE_STREAM_REPORT'):
   path=Path(os.environ['CRAFT_SERVE_STREAM_REPORT']);prior=json.loads(path.read_text()) if path.exists() else {'status':'PASS','scope':'Actual public cli.py serve stdio, verified craft.5, no TCP or aggregate interior claim','cases':[]};prior['cases']+=records;path.write_text(json.dumps(prior,indent=2)+'\n')

if __name__=='__main__':unittest.main()
