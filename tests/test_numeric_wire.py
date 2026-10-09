"""原生JSON词法及ID数值边界；共享健康原生进程，无GUI。"""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import threading
from test_serve_tcp import Client
from test_stream_launch import NATIVE_OBSERVER

ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=ROOT/'skills/photocraft-use/scripts'

def load(name):
    spec=importlib.util.spec_from_file_location('numeric_test_'+name,SCRIPTS/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def numeric_id(count=120000):return '['+','.join(['1e6']*count)+']'


def request(identifier,method='methods',params=None):
    return '{"id":'+identifier+',"method":'+json.dumps(method)+((',"params":'+json.dumps(params,separators=(',',':'))) if params is not None else '')+'}\n'


class NumericWire(unittest.TestCase):
    def test_forwarded_valid_numeric_id_does_not_expand_past_native_request_budget(self):
        stream=load('serve_stream');raw=request(numeric_id());message=stream.preflight(raw)
        class Process:stdin=io.BytesIO()
        wire=object.__new__(stream.Wire);wire.process=Process();wire.send(message)
        data=wire.process.stdin.getvalue()
        self.assertLess(len(raw.encode()),1<<20)
        self.assertLessEqual(len(data),1<<20)
        self.assertIn(b'1e6',data)
        self.assertEqual(json.loads(data),json.loads(raw))

    def test_batch_child_preserves_numeric_id_and_parameter_tokens(self):
        stream=load('serve_stream');raw='{"id":'+numeric_id()+',"method":"batch","params":{"steps":[{"command":"file.new","params":{"width":16,"height":16,"resolution":1e2}}]}}\n'
        message=stream.preflight(raw);sent=[]
        class Wire:
            timeout=120
            def send(self,child):
                class Process:stdin=io.BytesIO()
                wire=object.__new__(stream.Wire);wire.process=Process();wire.send(child);sent.append(wire.process.stdin.getvalue())
            def receive(self,child,output):return {'id':child['id'],'ok':True,'result':{}}
        stream.transact(Wire(),message,None,[])
        self.assertEqual(len(sent),1);self.assertLessEqual(len(sent[0]),1<<20)
        self.assertIn(b'1e6',sent[0]);self.assertIn(b'1e2',sent[0])

    def test_aggregate_response_reserves_actual_expanded_echo_id_before_later_edit(self):
        stream=load('serve_stream');raw=request(numeric_id(240000),'batch',{'steps':[{'method':'methods'},{'method':'doc.new','params':{'width':16,'height':16}}]})
        message=stream.preflight(raw);sent=[]
        class Wire:
            timeout=120
            def send(self,child):sent.append(child)
            def receive(self,child,output):return {'id':child['id'],'ok':True,'result':['x'*(6<<20)]}
        with self.assertRaisesRegex(RuntimeError,'serve_batch_response_budget'):
            stream.transact(Wire(),message,None,[])
        self.assertEqual(len(sent),1)

    def test_tcp_utf8_response_encoding_keeps_actual_success_frame_budget(self):
        tcp=load('serve_tcp');reply={'id':'汉'*180000,'ok':True,'result':['x'*(7<<20)]}
        self.assertLess(len(json.dumps(reply,ensure_ascii=False,separators=(',',':')).encode())+1,8<<20)
        output=io.BytesIO();tcp.emit(output,reply)
        self.assertLessEqual(len(output.getvalue()),8<<20)
        self.assertEqual(json.loads(output.getvalue()),reply)

    def test_native_id_echo_semantics_keep_negative_zero_and_float_fallback(self):
        stream=load('serve_stream')
        cases=[('-0',-0.0),('18446744073709551616',float(18446744073709551616)),('-9223372036854775809',float(-9223372036854775809)),('[true,1,1.0,-0]',[True,1,1.0,-0.0])]
        for literal,expected in cases:
            message=stream.preflight(request(literal))
            self.assertTrue(stream.same_id(getattr(message,'native_id',message['id']),expected),literal)
        self.assertFalse(stream.same_id(True,1));self.assertFalse(stream.same_id(1,1.0))


@unittest.skipUnless(os.environ.get('CRAFT_NATIVE_COMMANDS')=='1','requires actual pinned native runtime')
class NativeNumericWire(unittest.TestCase):
    def test_stdio_numeric_ids_and_batch_save_reopen_share_one_native_process(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);observer=root/'observer.py';observer.write_text(NATIVE_OBSERVER);counts=root/'counts.json'
            batch={'steps':[{'method':'doc.new','params':{'width':16,'height':16}},{'method':'doc.save','params':{'path':'saved.pcraft'}},{'method':'doc.open','params':{'path':'saved.pcraft'}},{'method':'doc.inspect'}]}
            rows=[request(numeric_id()),request('-0'),request('18446744073709551616'),request('-9223372036854775809'),request(numeric_id(),'batch',batch)]
            result=subprocess.run([sys.executable,'-I','-B',str(observer),str(SCRIPTS/'cli.py'),str(counts),'--runtime-home',os.environ['CRAFT_RUNTIME_HOME'],'--','serve','--automation-read-root',str(root),'--automation-write-root',str(root)],input=''.join(rows),capture_output=True,text=True,timeout=60)
            self.assertEqual(result.returncode,0,result.stdout[-700:]+result.stderr[-500:])
            replies=[json.loads(line) for line in result.stdout.splitlines()];self.assertEqual(len(replies),5)
            self.assertTrue(all(row['ok'] for row in replies));self.assertEqual(replies[-1]['result']['completed'],4)
            self.assertEqual(json.loads(counts.read_text()),{'started':1,'stopped':True});self.assertTrue((root/'saved.pcraft').is_file())
            record({'transport':'stdio','status':'PASS','nativeProcesses':1,'stopped':True,'guiLaunches':0,'requests':5,'batchSteps':4,'numericIdElements':120000,'largestRequestBytes':max(len(row.encode()) for row in rows),'savedReopened':True,'savedSha256':hashlib.sha256((root/'saved.pcraft').read_bytes()).hexdigest()})


    def test_tcp_clients_keep_numeric_frames_and_share_one_native_process(self):
        installed=json.loads(subprocess.check_output([sys.executable,'-I','-B',str(SCRIPTS/'bootstrap.py'),'--runtime-home',os.environ['CRAFT_RUNTIME_HOME']],text=True))
        tcp=load('serve_tcp')
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);gateway=tcp.Gateway(['serve','--automation-read-root',str(root),'--automation-write-root',str(root)],lambda:installed)
            server=tcp.Server(('127.0.0.1',0),'a'*64,gateway);thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':0.02});thread.start();process=None
            try:
                with Client(server.server_address) as first:
                    self.assertTrue(first.auth('a'*64)['ok']);self.assertIsNone(gateway.wire)
                    first.socket.sendall(request(numeric_id()).encode());reply=first.read();self.assertTrue(reply['ok'],str(reply)[-500:]);process=gateway.wire.process
                with Client(server.server_address) as second:
                    self.assertTrue(second.auth('a'*64)['ok'])
                    batch={'steps':[{'method':'doc.new','params':{'width':16,'height':16}},{'method':'doc.save','params':{'path':'saved.pcraft'}},{'method':'doc.open','params':{'path':'saved.pcraft'}},{'method':'doc.inspect'}]}
                    second.socket.sendall(request(numeric_id(),'batch',batch).encode());data=second.reader.readline();self.assertLessEqual(len(data),8<<20);reply=json.loads(data);self.assertTrue(reply['ok'],str(reply)[-500:]);self.assertEqual(reply['result']['completed'],4);self.assertIs(gateway.wire.process,process)
                self.assertTrue((root/'saved.pcraft').is_file())
            finally:
                server.shutdown();server.server_close();gateway.close();thread.join(timeout=5)
            self.assertIsNotNone(process);self.assertIsNotNone(process.poll());self.assertFalse(thread.is_alive())
            record({'transport':'tcp','status':'PASS','clients':2,'nativeProcesses':1,'stopped':True,'guiLaunches':0,'batchSteps':4,'numericIdElements':120000,'savedReopened':True,'savedSha256':hashlib.sha256((root/'saved.pcraft').read_bytes()).hexdigest()})


def record(case):
    target=os.environ.get('CRAFT_NUMERIC_WIRE_REPORT')
    if not target:return
    path=Path(target);value=json.loads(path.read_text()) if path.exists() else {'status':'PASS','cases':[]}
    value['cases'].append(case);path.write_text(json.dumps(value,indent=2)+'\n')


if __name__=='__main__':unittest.main()
