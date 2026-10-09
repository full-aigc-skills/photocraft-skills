"""固定rmcp生命周期：预初始化ping、首请求元数据及已知通知类型。"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from test_native_cli_preflight import OBSERVER
from test_stream_launch import NATIVE_OBSERVER

ROOT=Path(__file__).resolve().parents[1];SCRIPTS=ROOT/'skills/photocraft-use/scripts'
META={'io.modelcontextprotocol/protocolVersion':'2026-07-28','io.modelcontextprotocol/clientCapabilities':{}}

def load(name):
    spec=importlib.util.spec_from_file_location('lifecycle_test_'+name,SCRIPTS/(name+'.py'));module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def invalid_messages():
    cases=[]
    for identifier in [2**63,-(2**63)-1]:cases.append((json.dumps({'jsonrpc':'2.0','id':identifier,'method':'ping'}),'$.id'))
    cases.append(('{"jsonrpc":"2.0","id":-0,"method":"ping"}','$.id'))
    for params,path in [(None,'$.params._meta'),({'_meta':[]},'$.params._meta'),({'_meta':{}},'$.params._meta["io.modelcontextprotocol/protocolVersion"]'),({'_meta':{**META,'io.modelcontextprotocol/protocolVersion':1}},'$.params._meta["io.modelcontextprotocol/protocolVersion"]'),({'_meta':{'io.modelcontextprotocol/protocolVersion':'2026-07-28'}},'$.params._meta["io.modelcontextprotocol/clientCapabilities"]'),({'_meta':{**META,'io.modelcontextprotocol/clientCapabilities':[]}},'$.params._meta["io.modelcontextprotocol/clientCapabilities"]'),({'cursor':[]},'$.params.cursor')]:
        cases.append((json.dumps({'jsonrpc':'2.0','id':'list','method':'tools/list','params':params}),path))
    for method,params,path in [('notifications/progress',{},'$.params.progressToken'),('notifications/progress',{'progressToken':False,'progress':1},'$.params.progressToken'),('notifications/progress',{'progressToken':1,'progress':True},'$.params.progress'),('notifications/progress',{'progressToken':1,'progress':1,'total':[]},'$.params.total'),('notifications/progress',{'progressToken':1,'progress':1,'message':1},'$.params.message'),('notifications/cancelled',{'requestId':[]},'$.params.requestId'),('notifications/cancelled',{'reason':False},'$.params.reason'),('notifications/cancelled',{'_meta':[]},'$.params._meta')]:
        cases.append((json.dumps({'jsonrpc':'2.0','method':method,'params':params}),path))
    cases.append((json.dumps({'jsonrpc':'2.0','method':'notifications/initialized'}),'$.method'))
    return cases

class MCPPreflightLifecycle(unittest.TestCase):
    def test_lifecycle_invalid_first_messages_refuse_before_install_in_all_skills(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);observer=root/'observer.py';observer.write_text(OBSERVER)
            for scripts in sorted((ROOT/'skills').glob('*/scripts')):
                for raw,path in invalid_messages():
                    with self.subTest(skill=scripts.parent.name,path=path):
                        counts=root/'counts.json';result=subprocess.run([sys.executable,'-I','-B',str(observer),str(scripts/'cli.py'),str(counts),'--runtime-home',str(root/'runtime'),'--','mcp'],input=raw+'\n',capture_output=True,text=True,timeout=20)
                        self.assertEqual(json.loads(counts.read_text()),{'install':0,'session':0},result.stderr[-500:])
                        self.assertEqual(result.returncode,1,result.stdout[-500:]);detail=json.loads(result.stdout)['error']['data'];self.assertEqual(detail['fieldPath'],path);self.assertEqual(detail['outcome'],'not_executed');self.assertEqual(detail['phase'],'validation');self.assertFalse(detail['replayAllowed']);self.assertFalse((root/'runtime').exists())

    def test_valid_ping_metadata_extensions_and_notifications_keep_native_shapes(self):
        stream=load('mcp_stream')
        valid=[{'jsonrpc':'2.0','id':-(2**63),'method':'ping','params':None},{'jsonrpc':'2.0','id':2**63-1,'method':'tools/list','params':{'cursor':None,'_meta':META,'future':[]}}, {'jsonrpc':'2.0','method':'notifications/progress','params':{'progressToken':'p','progress':-1.5,'total':None,'message':None,'future':[]}},{'jsonrpc':'2.0','method':'notifications/cancelled','params':{'requestId':None,'reason':None,'_meta':{'vendor':[]}}}]
        for message in valid:self.assertEqual(stream.preflight(json.dumps(message)),message)

@unittest.skipUnless(os.environ.get('CRAFT_NATIVE_COMMANDS')=='1','requires pinned native runtime')
class NativeMCPLifecycle(unittest.TestCase):
    def test_preinit_pings_and_legacy_or_metadata_modes_reuse_single_process(self):
        reports=[]
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);observer=root/'observer.py';observer.write_text(NATIVE_OBSERVER)
            for mode in ['legacy','metadata']:
                counts=root/(mode+'-counts.json');saved=mode+'.pcraft'
                messages=[{'jsonrpc':'2.0','id':'pre-ping','method':'ping'}]
                if mode=='legacy':messages.append({'jsonrpc':'2.0','id':'init','method':'initialize','params':{'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'life','version':'1'}}})
                messages.append({'jsonrpc':'2.0','id':'list','method':'tools/list','params':{'_meta':{**META,'vendor/data':[]}} if mode=='metadata' else None})
                messages.extend([{'jsonrpc':'2.0','method':'notifications/progress','params':{'progressToken':'done','progress':-1.0,'total':None,'message':None}},{'jsonrpc':'2.0','method':'notifications/cancelled','params':{'requestId':None,'reason':None}}])
                for index,(name,args) in enumerate([('doc_new',{'width':16,'height':16}),('doc_save',{'path':saved}),('doc_open',{'path':saved}),('doc_inspect',{})]):
                    messages.append({'jsonrpc':'2.0','id':index,'method':'tools/call','params':{'name':name,'arguments':args,**({'_meta':META} if mode=='metadata' else {})}})
                result=subprocess.run([sys.executable,'-I','-B',str(observer),str(SCRIPTS/'cli.py'),str(counts),'--runtime-home',os.environ['CRAFT_RUNTIME_HOME'],'--','mcp','--automation-read-root',str(root),'--automation-write-root',str(root)],input=''.join(json.dumps(row)+'\n' for row in messages),capture_output=True,text=True,timeout=30)
                self.assertEqual(result.returncode,0,result.stdout[-700:]+result.stderr[-500:]);replies=[json.loads(line) for line in result.stdout.splitlines()];self.assertTrue(all('result' in row for row in replies));self.assertEqual(json.loads(counts.read_text()),{'started':1,'stopped':True});self.assertTrue((root/saved).is_file());reports.append({'mode':mode,'status':'PASS','nativeProcesses':1,'savedReopened':True,'requests':len(messages),'replies':len(replies),'stopped':True})
        if os.environ.get('CRAFT_MCP_LIFECYCLE_REPORT'):Path(os.environ['CRAFT_MCP_LIFECYCLE_REPORT']).write_text(json.dumps({'status':'PASS','cases':reports,'guiLaunches':0},indent=2)+'\n')

if __name__=='__main__':unittest.main()
