"""MCP公开流在安装前拒绝无效首请求，回复失效后不发送下一编辑。"""
import importlib.util,io,json,sys,unittest
from pathlib import Path
from unittest.mock import patch
SCRIPTS=Path(__file__).resolve().parents[1]/'skills/photocraft-use/scripts'
def load(name,scripts=SCRIPTS):
 spec=importlib.util.spec_from_file_location('stream_test_'+name,scripts/(name+'.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
class PublicStreamPreflight(unittest.TestCase):
 def test_invalid_first_stream_message_never_installs_or_launches(self):
  for scripts in sorted(SCRIPTS.parents[1].glob('*/scripts')):
   for raw in ['{"id":1,"id":2,"method":"tools/call"}\n',json.dumps({'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'command_run','arguments':{'id':'layer.new.layer','params':{'opacity':'bad'}}}})+'\n']:
    with self.subTest(raw=raw):
     for extra in [[],['--help'],['-h']]:
      cli=load('cli',scripts);original=importlib.util.spec_from_file_location;calls=[]
      def observe(name,path,*a,**k):
       spec=original(name,path,*a,**k);execute=spec.loader.exec_module
       def hooked(module):
        execute(module)
        if Path(path).name=='bootstrap.py':
         def forbidden(*a,**k):calls.append('install');raise AssertionError('invalid stream installed runtime')
         module.install=forbidden
       spec.loader.exec_module=hooked;return spec
      output=io.StringIO()
      with patch.object(sys,'argv',['cli.py','--','mcp',*extra]),patch.object(sys,'stdin',io.StringIO(raw)),patch.object(sys,'stdout',output),patch.object(importlib.util,'spec_from_file_location',side_effect=observe):code=cli.main()
      self.assertEqual(code,1);self.assertEqual(calls,[]);reply=json.loads(output.getvalue());self.assertEqual(reply['error']['data']['outcome'],'not_executed');self.assertFalse(reply['error']['data']['retryable'])

class StreamContract(unittest.TestCase):
 def test_native_optional_null_parameters_preserve_wire_message(self):
  stream=load('mcp_stream')
  for message in [{'jsonrpc':'2.0','id':'list','method':'tools/list','params':None},{'jsonrpc':'2.0','id':'sessions','method':'tools/call','params':{'name':'session_list','arguments':None}}]:
   with self.subTest(message=message):self.assertEqual(stream.preflight(json.dumps(message)),message)
 def test_invalid_command_container_and_unknown_tool_are_static_errors(self):
  stream=load('mcp_stream')
  for name,args in [('command_run',{'id':'layer.new.layer','params':[]}),('not_a_tool',{})]:
   with self.subTest(name=name),self.assertRaises(ValueError):stream.preflight(json.dumps({'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':name,'arguments':args}}))
 def test_semantic_reply_stops_before_reading_or_sending_next_edit(self):
  stream=load('mcp_stream');messages=[{'jsonrpc':'2.0','id':'save','method':'tools/call','params':{'name':'doc_save','arguments':{'path':'saved.pcraft'}}},{'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'command_run','arguments':{'id':'layer.new.layer','params':{'name':'Never'}}}}];sent=[]
  class Wire:
   def __init__(self,argv):pass
   def send(self,message):sent.append(message)
   def receive(self,message,output):return {'jsonrpc':'2.0','id':message['id'],'result':{'content':[{'type':'text','text':'{"error":"native failure"}'}]}}
   def close(self):sent.append('closed')
  out=io.StringIO()
  with patch.object(stream,'Wire',Wire):code=stream.run(['mcp'],lambda:{'executable':'verified','binarySha256':'a'*64},io.StringIO(''.join(json.dumps(m)+'\n' for m in messages)),out)
  self.assertEqual(code,1);self.assertEqual(sent,[messages[0],'closed']);error=json.loads(out.getvalue())['error']['data'];self.assertEqual(error['outcome'],'failed');self.assertEqual(error['phase'],'reply_received');self.assertEqual(error['receipts'],[]);self.assertFalse(error['replayAllowed'])
 def test_valid_native_image_reply_is_not_narrowed_to_json(self):
  stream=load('mcp_stream');request={'method':'tools/call','params':{'name':'doc_render_preview','arguments':{}}};result={'content':[{'type':'image','data':'AA==','mimeType':'image/png'}]};stream.validate_reply(request,{'result':result})

import hashlib,os,subprocess,tempfile
@unittest.skipUnless(os.environ.get('CRAFT_MCP_STREAM_NATIVE')=='1','explicit real native stream opt-in')
class NativeStream(unittest.TestCase):
 def test_actual_public_mcp_post_save_faults_preserve_source_and_stop_next_edit(self):
  self.verify(['duplicate','nonfinite','semantic','wrong-id','extra-frame','malformed-error'])
 def test_actual_public_mcp_healthy_string_ids_notifications_and_legacy_replies(self):
  self.verify([None])
 def verify(self,faults):
  cli=load('cli');original_spec=importlib.util.spec_from_file_location;runtime=os.environ['CRAFT_RUNTIME_HOME'];records=[]
  with tempfile.TemporaryDirectory(prefix='photo-mcp-stream-') as tmp:
   root=Path(tmp);source=root/'original.pcraft'
   create=subprocess.run([sys.executable,'-I','-B',str(SCRIPTS/'cli.py'),'--runtime-home',runtime,'--','run','--new={"width":32,"height":32}','--cmd=layer.new.layer','--params={"name":"Source"}','--out',str(source)],capture_output=True,text=True,timeout=30);self.assertEqual(create.returncode,0,create.stdout+create.stderr);source_sha=hashlib.sha256(source.read_bytes()).hexdigest()
   for fault in faults:
    saved=root/((fault or 'healthy')+'.pcraft');sent=[];seen=[]
    def observe(name,path,*a,**k):
     spec=original_spec(name,path,*a,**k);execute=spec.loader.exec_module
     def hooked(module):
      execute(module)
      if Path(path).name=='mcp_stream.py':
       original_read=module.Wire.read_line;original_send=module.Wire.send
       def send(wire,message):sent.append(message);return original_send(wire,message)
       def read(wire,deadline):
        raw=original_read(wire,deadline);reply=json.loads(raw);seen.append(reply.get('id'))
        if reply.get('id')==4 and fault:
         if fault=='duplicate':return b'{"jsonrpc":"2.0",'+raw[1:]
         if fault=='nonfinite':return b'{"probe":NaN,'+raw[1:]
         if fault=='semantic':reply['result']={'content':[{'type':'text','text':'{"error":"injected native semantic failure"}'}]}
         elif fault=='wrong-id':reply['id']='unrelated'
         elif fault=='malformed-error':reply.pop('result');reply['error']={'code':'bad','message':7}
         elif fault=='extra-frame':wire.buffer=json.dumps(reply).encode()+b'\n'+wire.buffer
         return json.dumps(reply).encode()
        return raw
       module.Wire.send=send;module.Wire.read_line=read
     spec.loader.exec_module=hooked;return spec
    messages=[{'jsonrpc':'2.0','id':'init','method':'initialize','params':{'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'stream-test','version':'1'}}},{'jsonrpc':'2.0','method':'notifications/initialized'},{'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'doc_open','arguments':{'path':source.name}}},{'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'command_run','arguments':{'id':'layer.new.layer','params':{'name':'Preserved'}}}},{'jsonrpc':'2.0','id':4,'method':'tools/call','params':{'name':'doc_save','arguments':{'path':saved.name}}},{'jsonrpc':'2.0','id':5,'method':'tools/call','params':{'name':'command_run','arguments':{'id':'layer.renameLayer','params':{'name':'Never'}}}}]
    if fault is None:messages.extend([{'jsonrpc':'2.0','id':'preview','method':'tools/call','params':{'name':'doc_render_preview','arguments':{}}},{'jsonrpc':'2.0','id':'list','method':'tools/list','params':None},{'jsonrpc':'2.0','id':'sessions','method':'tools/call','params':{'name':'session_list','arguments':None}}])
    out=io.StringIO()
    with patch.object(sys,'argv',['cli.py','--runtime-home',runtime,'--','mcp','--automation-read-root',str(root),'--automation-write-root',str(root)]),patch.object(sys,'stdin',io.StringIO(''.join(json.dumps(m)+'\n' for m in messages))),patch.object(sys,'stdout',out),patch.object(importlib.util,'spec_from_file_location',side_effect=observe):code=cli.main()
    replies=[json.loads(line) for line in out.getvalue().splitlines()]
    self.assertEqual(code,1 if fault else 0,out.getvalue());self.assertEqual([m.get('id') for m in sent],['init',None,2,3,4]+([] if fault else [5,'preview','list','sessions']));self.assertEqual(replies[0]['id'],'init')
    if fault:
     error=replies[-1]['error']['data'];self.assertEqual(error['outcome'],'failed' if fault=='semantic' else 'unknown');self.assertEqual(error['phase'],'reply_received');self.assertFalse(error['replayAllowed']);self.assertFalse(error['retryable']);self.assertEqual(error['request']['id'],4);self.assertEqual(len(error['receipts']),3)
    else:
     self.assertEqual([r['id'] for r in replies],['init',2,3,4,5,'preview','list','sessions']);self.assertEqual(replies[-3]['result']['content'][0]['type'],'image')
    self.assertTrue(saved.exists());saved_sha=hashlib.sha256(saved.read_bytes()).hexdigest();reopen=subprocess.run([sys.executable,'-I','-B',str(SCRIPTS/'cli.py'),'--runtime-home',runtime,'--','info',str(saved)],capture_output=True,text=True,timeout=30);self.assertEqual(reopen.returncode,0,reopen.stderr);layers=json.loads(reopen.stdout)['layers'];self.assertTrue(any(l['name']=='Preserved' for l in layers));self.assertFalse(any(l['name']=='Never' for l in layers));self.assertEqual(hashlib.sha256(saved.read_bytes()).hexdigest(),saved_sha);self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),source_sha)
    records.append({'fault':fault,'status':'PASS','sentIds':[m.get('id') for m in sent],'observedReplyIds':seen,'savedReopened':True,'sourcePreserved':True,'savedSha256':saved_sha})
  if os.environ.get('CRAFT_MCP_STREAM_REPORT'):
   path=Path(os.environ['CRAFT_MCP_STREAM_REPORT']);prior=json.loads(path.read_text()) if path.exists() else {'status':'PASS','scope':'Actual cli.py mcp with verified craft.5; reply transport faults after actual native save; serve/TCP and aggregates excluded','cases':[]};prior['cases']+=records;path.write_text(json.dumps(prior,indent=2)+'\n')

class MetadataContract(unittest.TestCase):
 def test_bad_initialize_metadata_is_unknown_before_tools(self):
  stream=load('mcp_stream');request={'method':'initialize'}
  for reply in [None,{'protocolVersion':'2024-11-05','capabilities':{},'serverInfo':{'name':'photocraft','version':'wrong'}}]:
   with self.subTest(reply=reply),self.assertRaises(RuntimeError) as caught:stream.validate_reply(request,{'result':reply},'0.2.0-craft.5')
   self.assertEqual(caught.exception.outcome,'unknown');self.assertEqual(caught.exception.phase,'reply_received')
 def test_image_text_semantic_error_is_not_success(self):
  stream=load('mcp_stream')
  with self.assertRaises(RuntimeError) as caught:stream.validate_reply({'method':'tools/call','params':{'name':'ui_screenshot'}},{'result':{'content':[{'type':'text','text':'{"error":"failure"}'}]}})
  self.assertEqual(caught.exception.outcome,'failed')
  with self.assertRaises(RuntimeError) as caught:stream.validate_reply({'method':'tools/call','params':{'name':'ui_screenshot'}},{'result':{'content':[{'type':'text','text':'caption without any image'}]}})
  self.assertEqual(caught.exception.outcome,'unknown')

class EnvelopeContract(unittest.TestCase):
 def test_malformed_native_rpc_error_is_unknown(self):
  stream=load('mcp_stream');wire=stream.Wire.__new__(stream.Wire);wire.timeout=1
  for error in [None,[],{}, {'code':'bad','message':7}]:
   raw=json.dumps({'jsonrpc':'2.0','id':1,'error':error}).encode()
   with patch.object(wire,'read_line',return_value=raw),self.subTest(error=error),self.assertRaises(RuntimeError) as caught:wire.receive({'id':1},io.StringIO())
   self.assertEqual(caught.exception.outcome,'unknown');self.assertEqual(caught.exception.phase,'reply_received')
 def test_malformed_tools_list_is_unknown(self):
  stream=load('mcp_stream')
  for value in [[],{}, {'tools':[{'name':'tool','inputSchema':None}]}]:
   with self.subTest(value=value),self.assertRaises(RuntimeError):stream.validate_reply({'method':'tools/list'},{'result':value})

class StreamSetupDiagnostics(unittest.TestCase):
 def test_missing_bootstrap_keeps_local_recovery_without_launch(self):
  import shutil
  with tempfile.TemporaryDirectory() as temporary:
   scripts=Path(temporary)/'scripts';scripts.mkdir()
   for name in ['cli.py','mcp_stream.py','stream_launch.py','strict_json.py','operation_errors.py']:shutil.copyfile(SCRIPTS/name,scripts/name)
   message={'jsonrpc':'2.0','id':'init','method':'initialize','params':{}}
   result=subprocess.run([sys.executable,'-I','-B',str(scripts/'cli.py'),'--','mcp'],input=json.dumps(message)+'\n',capture_output=True,text=True)
   self.assertEqual(result.returncode,1,result.stdout+result.stderr);error=json.loads(result.stdout)['error']['data'];self.assertEqual(error['outcome'],'not_executed');self.assertEqual(error['dependencySetup']['bootstrapScript'],str((scripts/'bootstrap.py').resolve()));self.assertNotIn('Traceback',result.stderr)

if __name__=='__main__':unittest.main()
