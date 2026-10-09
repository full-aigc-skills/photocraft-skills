"""公开TCP入口配置拒绝先于安装，认证客户端共用受监督的原生会话。"""
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
SCRIPTS=Path(__file__).resolve().parents[1]/'skills/photocraft-use/scripts'
def load(name,scripts=None):
 spec=importlib.util.spec_from_file_location('tcp_test_'+name,(scripts or SCRIPTS)/(name+'.py'));module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
class TCPPreflight(unittest.TestCase):
 def test_invalid_public_tcp_configuration_never_installs(self):
  for scripts in sorted(SCRIPTS.parents[1].glob('*/scripts')):
   for argv in [['serve','--port','bad'],['serve','--port','65536'],['serve','--port','0','--control-token','bad']]:
    with self.subTest(skill=scripts.parent.name,argv=argv):
     cli=load('cli',scripts);original=importlib.util.spec_from_file_location;calls=[]
     def observe(name,path,*args,**kwargs):
      spec=original(name,path,*args,**kwargs);execute=spec.loader.exec_module
      def hooked(module):
       execute(module)
       if Path(path).name=='bootstrap.py':
        def forbidden(*args,**kwargs):calls.append('install');raise AssertionError('invalid TCP launch installed runtime')
        module.install=forbidden
      spec.loader.exec_module=hooked;return spec
     output=io.StringIO()
     with patch.object(sys,'argv',['cli.py','--',*argv]),patch.object(sys,'stdout',output),patch.object(importlib.util,'spec_from_file_location',side_effect=observe):code=cli.main()
     self.assertEqual(code,1);self.assertEqual(calls,[]);detail=json.loads(output.getvalue())['errorData'];self.assertEqual(detail['outcome'],'not_executed');self.assertEqual(detail['phase'],'validation')


class TCPFailureContract(unittest.TestCase):
 def test_install_subprocess_failure_is_structured_without_native_start(self):
  import subprocess
  tcp=load('serve_tcp')
  def fail():raise subprocess.CalledProcessError(2,['installer'])
  gateway=tcp.Gateway(['serve'],fail)
  try:
   reply,keep=gateway.execute({'id':1,'method':'methods'})
   self.assertFalse(keep);self.assertFalse(reply['ok']);self.assertEqual(reply['errorData']['outcome'],'not_executed');self.assertFalse(reply['errorData']['replayAllowed']);self.assertIsNone(gateway.wire)
  finally:gateway.close()


import contextlib
import hashlib
import os
import re
import select
import signal
import socket
import subprocess
import tempfile
import threading
import time

class Client:
 def __init__(self,address):
  self.socket=socket.create_connection(address,timeout=5);self.reader=self.socket.makefile('rb')
 def send(self,message):self.socket.sendall((json.dumps(message)+'\n').encode())
 def read(self):return json.loads(self.reader.readline())
 def call(self,message):self.send(message);return self.read()
 def auth(self,token):return self.call({'id':'auth','method':'auth','params':{'token':token}})
 def close(self):self.reader.close();self.socket.close()
 def __enter__(self):return self
 def __exit__(self,*args):self.close()

@contextlib.contextmanager
def boundary_server():
 tcp=load('serve_tcp');calls=[]
 def forbidden():calls.append('install');raise AssertionError('boundary started native session')
 gateway=tcp.Gateway(['serve'],forbidden);server=tcp.Server(('127.0.0.1',0),'a'*64,gateway);thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':0.02});thread.start()
 try:yield server.server_address,calls
 finally:server.shutdown();server.server_close();gateway.close();thread.join(timeout=5)

class TCPProtocolBoundary(unittest.TestCase):
 def test_authentication_and_invalid_unicode_token_never_install(self):
  with boundary_server() as (address,calls):
   for message in [{'id':1,'method':'methods'},{'id':1,'method':'auth','params':{'token':'bad'}},{'id':1,'method':'auth','params':{'token':'\ud800'*64}}]:
    with self.subTest(message=message),Client(address) as client:
     reply=client.call(message);self.assertFalse(reply['ok']);self.assertEqual(reply['error'],'authentication required');self.assertNotIn('errorData',reply)
   with Client(address) as client:self.assertTrue(client.auth('A'*64)['ok'])
   self.assertEqual(calls,[])
 def test_authenticated_invalid_request_never_installs(self):
  with boundary_server() as (address,calls),Client(address) as client:
   self.assertTrue(client.auth('a'*64)['ok']);reply=client.call({'id':1,'method':'doc.new','params':{'width':'bad'}})
   self.assertFalse(reply['ok']);self.assertEqual(reply['errorData']['outcome'],'not_executed');self.assertEqual(calls,[])
 def test_oversized_request_closes_connection_before_authentication_or_install(self):
  with boundary_server() as (address,calls),Client(address) as client:
   client.socket.sendall(b' '*(1048576+1)+b'\n');reply=client.read();self.assertEqual(reply['error'],'request exceeds 1048576 bytes');self.assertEqual(calls,[])
 def test_native_idle_timeout_closes_unauthenticated_connection_without_install(self):
  with boundary_server() as (address,calls),Client(address) as client:
   client.socket.settimeout(35);started=time.monotonic();self.assertEqual(client.reader.readline(),b'');elapsed=time.monotonic()-started
   self.assertGreaterEqual(elapsed,27);self.assertLess(elapsed,35);self.assertEqual(calls,[])
 def test_sixteenth_connection_allowed_seventeenth_refused_without_install(self):
  with boundary_server() as (address,calls),contextlib.ExitStack() as stack:
   clients=[stack.enter_context(Client(address)) for _ in range(16)]
   for client in clients:self.assertTrue(client.auth('a'*64)['ok'])
   with Client(address) as extra:self.assertEqual(extra.read()['error'],'connection limit reached')
   self.assertEqual(calls,[])

class TCPLaunchCompatibility(unittest.TestCase):
 def test_native_unsigned_port_literals_keep_plus_and_leading_zero_compatibility(self):
  tcp=load('serve_tcp')
  for text,expected in [('+0',0),('0'*5000,0),('0'*5000+'65535',65535),('+000065535',65535)]:
   with self.subTest(textLength=len(text)):self.assertEqual(tcp.launch(['serve','--port',text])[0],expected)
  for text in ['65536','0'*5000+'65536','-0']:
   with self.subTest(textLength=len(text)),self.assertRaises(ValueError):tcp.launch(['serve','--port',text])

class TCPTokenFiles(unittest.TestCase):
 def test_native_token_file_creation_reuse_and_environment_precedence(self):
  tcp=load('serve_tcp')
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary);path=root/'nested/token';token=tcp.server_token(None,path)
   self.assertRegex(token,'^[0-9a-f]{64}$');self.assertEqual(path.stat().st_mode&0o777,0o600);before=path.read_bytes();self.assertEqual(tcp.server_token(None,path),token);self.assertEqual(path.read_bytes(),before)
   with patch.dict(os.environ,{'PHOTOCRAFT_CONTROL_TOKEN':'B'*64},clear=True):self.assertEqual(tcp.launch(['serve','--port=0'])[1],'B'*64)
   with patch.dict(os.environ,{'PHOTOCRAFT_CONTROL_TOKEN_FILE':str(path)},clear=True):self.assertEqual(tcp.launch(['serve','--port','0'])[2],path)
   with patch.dict(os.environ,{'PHOTOCRAFT_CONTROL_TOKEN':'a'*64,'PHOTOCRAFT_CONTROL_TOKEN_FILE':str(path)},clear=True),self.assertRaises(ValueError):tcp.launch(['serve','--port','0'])

CHILD=r'''
import importlib.util,json,os,sys,time
from pathlib import Path
from unittest.mock import patch
scripts=Path(sys.argv[1]);runtime=sys.argv[2];root=Path(sys.argv[3]);fault=sys.argv[4];original=importlib.util.spec_from_file_location
spec=original('actual_public_cli',scripts/'cli.py');cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(cli)
def observe(name,path,*args,**kwargs):
 spec=original(name,path,*args,**kwargs);execute=spec.loader.exec_module
 def hooked(module):
  execute(module)
  if Path(path).name=='serve_stream.py':
   original_send=module.Wire.send;original_read=module.Wire.read_line
   def send(wire,message):
    with (root/'wire-events.jsonl').open('a') as log:log.write(json.dumps({'id':message.get('id'),'nativePid':wire.process.pid})+'\n')
    return original_send(wire,message)
   def read(wire,deadline):
    raw=original_read(wire,deadline);reply=json.loads(raw)
    if reply.get('id')==4 and fault not in {'healthy','delivery'}:
     if fault=='duplicate':return b'{"ok":true,'+raw[1:]
     if fault=='nonfinite':return b'{"probe":NaN,'+raw[1:]
     if fault=='semantic':reply['result']={'error':'injected semantic failure'}
     elif fault=='wrong-id':reply['id']='other'
     elif fault=='extra-frame':wire.buffer=json.dumps(reply).encode()+b'\n'+wire.buffer
     elif fault=='malformed-error':reply.pop('result');reply['ok']=False;reply['error']={'bad':'shape'}
     elif fault=='missing-ok':reply.pop('ok')
     return json.dumps(reply).encode()
    return raw
   module.Wire.send=send;module.Wire.read_line=read
  if Path(path).name=='serve_tcp.py' and fault=='delivery':
   original_emit=module.emit
   def emit(output,reply):
    if reply.get('id')==4 and reply.get('ok'):
     (root/'delivery-ready').write_text('ready');deadline=time.monotonic()+15
     while not (root/'release-delivery').exists() and time.monotonic()<deadline:time.sleep(0.01)
     raise BrokenPipeError('injected delivery loss after actual native save')
    return original_emit(output,reply)
   module.emit=emit
 spec.loader.exec_module=hooked;return spec
sys.argv=['cli.py','--runtime-home',runtime,'--','serve','--port','0','--control-token','a'*64,'--automation-read-root',str(root),'--automation-write-root',str(root)]
with patch.object(importlib.util,'spec_from_file_location',side_effect=observe):raise SystemExit(cli.main())
'''

@unittest.skipUnless(os.environ.get('CRAFT_SERVE_TCP_NATIVE')=='1','explicit actual native TCP supervision opt-in')
class NativeTCP(unittest.TestCase):
 def test_healthy_two_connections_share_actual_native_document(self):self.verify(['healthy'])
 def test_actual_post_save_faults_quarantine_other_connection_and_preserve_files(self):self.verify(['duplicate','nonfinite','semantic','wrong-id','extra-frame','malformed-error','missing-ok'])
 def test_delivery_loss_holds_shared_gate_before_other_connection_edit(self):self.verify(['delivery'])
 def verify(self,faults):
  runtime=os.environ['CRAFT_RUNTIME_HOME'];records=[]
  for fault in faults:
   with tempfile.TemporaryDirectory(prefix='photo-serve-tcp-') as temporary:
    root=Path(temporary);source=root/'original.pcraft';saved=root/'saved.pcraft'
    create=subprocess.run([sys.executable,'-I','-B',str(SCRIPTS/'cli.py'),'--runtime-home',runtime,'--','run','--new={"width":32,"height":32}','--cmd=layer.new.layer','--params={"name":"Source"}','--out',str(source)],capture_output=True,text=True,timeout=30);self.assertEqual(create.returncode,0,create.stdout+create.stderr);source_sha=hashlib.sha256(source.read_bytes()).hexdigest()
    process=subprocess.Popen([sys.executable,'-B','-c',CHILD,str(SCRIPTS),runtime,str(root),fault],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
    try:
     self.assertTrue(select.select([process.stderr],[],[],10)[0],'TCP readiness timeout');line=process.stderr.readline();match=re.fullmatch(r'photocraft-cli serving on 127\.0\.0\.1:(\d+)\n',line);self.assertIsNotNone(match,line);address=('127.0.0.1',int(match[1]))
     with Client(address) as first,Client(address) as second:
      self.assertTrue(first.auth('a'*64)['ok']);self.assertTrue(second.auth('a'*64)['ok']);self.assertTrue(first.call({'id':2,'method':'doc.open','params':{'path':source.name}})['ok']);self.assertTrue(second.call({'id':3,'method':'engine.execute','params':{'command':'layer.new.layer','params':{'name':'Preserved'}}})['ok'])
      save={'id':4,'method':'doc.save','params':{'path':saved.name}};next_edit={'id':5,'method':'engine.execute','params':{'command':'layer.renameLayer','params':{'name':'Never'}}}
      if fault=='delivery':
       first.send(save);deadline=time.monotonic()+10
       while not (root/'delivery-ready').exists() and time.monotonic()<deadline:time.sleep(0.01)
       self.assertTrue((root/'delivery-ready').exists());second.send(next_edit)
       try:self.assertFalse(select.select([second.socket],[],[],0.2)[0],'second edit escaped before delivery was resolved')
       finally:(root/'release-delivery').write_text('release')
       later=second.read();self.assertFalse(later['ok']);self.assertEqual(later['error'],'serve_session_quarantined');self.assertEqual(later['errorData']['outcome'],'not_executed');self.assertEqual(later['errorData']['priorFailure']['phase'],'reply_validated')
      else:
       reply=first.call(save)
       if fault=='healthy':
        self.assertTrue(reply['ok']);self.assertTrue(second.call(next_edit)['ok']);image=first.call({'id':{'image':[1,True]},'method':'doc.render','params':{'maxSide':16}});self.assertEqual(image['result']['mime'],'image/png');self.assertEqual(image['id'],{'image':[1,True]})
       else:
        self.assertFalse(reply['ok']);detail=reply['errorData'];self.assertEqual(detail['outcome'],'failed' if fault=='semantic' else 'unknown');self.assertEqual(detail['phase'],'reply_received');self.assertFalse(detail['replayAllowed']);self.assertEqual(len(detail['receipts']),2)
        later=second.call(next_edit);self.assertFalse(later['ok']);self.assertEqual(later['error'],'serve_session_quarantined');self.assertEqual(later['errorData']['outcome'],'not_executed')
      self.assertTrue(saved.is_file());saved_sha=hashlib.sha256(saved.read_bytes()).hexdigest();reopen=subprocess.run([sys.executable,'-I','-B',str(SCRIPTS/'cli.py'),'--runtime-home',runtime,'--','info',str(saved)],capture_output=True,text=True,timeout=30);self.assertEqual(reopen.returncode,0,reopen.stdout+reopen.stderr);layers=json.loads(reopen.stdout)['layers'];self.assertTrue(any(layer['name']=='Preserved' for layer in layers));self.assertFalse(any(layer['name']=='Never' for layer in layers));self.assertEqual(hashlib.sha256(saved.read_bytes()).hexdigest(),saved_sha);self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),source_sha)
      sent=[json.loads(line)['id'] for line in (root/'wire-events.jsonl').read_text().splitlines()];self.assertEqual(sent,[2,3,4]+([5,{'image':[1,True]}] if fault=='healthy' else []));records.append({'fault':fault,'status':'PASS','sentIds':sent,'savedSha256':saved_sha,'sourcePreserved':True,'savedReopened':True,'sharedSession':True,'otherConnectionQuarantined':fault!='healthy'})
    finally:
     (root/'release-delivery').write_text('release')
     if process.poll() is None:process.terminate()
     try:stdout,stderr=process.communicate(timeout=5)
     except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);stdout,stderr=process.communicate(timeout=5)
     self.assertNotIn('Traceback',stderr,stderr);self.assertEqual(process.returncode,0,stderr)
     native_pids={json.loads(line)['nativePid'] for line in (root/'wire-events.jsonl').read_text().splitlines()}
     for pid in native_pids:
      with self.assertRaises(ProcessLookupError):os.kill(pid,0)
     if records:records[-1]['ownedNativeProcessesExited']=True
  if os.environ.get('CRAFT_SERVE_TCP_REPORT'):
   path=Path(os.environ['CRAFT_SERVE_TCP_REPORT']);prior=json.loads(path.read_text()) if path.exists() else {'status':'PASS','scope':'Actual public TCP frontend with pinned craft.5 shared native process; post-save faults and delivery barrier','cases':[]};prior['cases']+=records;path.write_text(json.dumps(prior,indent=2)+'\n')


if __name__=='__main__':unittest.main()
