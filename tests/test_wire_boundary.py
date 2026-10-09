"""固定原生MCP初始化与UTF-8请求边界；复用流式会话，不启动GUI。"""
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from test_native_cli_preflight import OBSERVER
from test_stream_launch import NATIVE_OBSERVER

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT/'skills/photocraft-use/scripts'
PARAMS = {'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'工艺','version':'1'}}


def load(name):
    spec=importlib.util.spec_from_file_location('boundary_test_'+name,SCRIPTS/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def invalid_initializations():
    cases=[({},'$.params.protocolVersion'),(None,'$.params'),([], '$.params'),(True,'$.params')]
    for key,value,path in [('protocolVersion',1,'$.params.protocolVersion'),
                           ('capabilities',[],'$.params.capabilities'),
                           ('clientInfo',{},'$.params.clientInfo.name'),
                           ('clientInfo',{'name':'x','version':True},'$.params.clientInfo.version'),
                           ('clientInfo',{'name':'x','version':'1','icons':[{'src':1}]},'$.params.clientInfo.icons[0].src'),
                           ('clientInfo',{'name':'x','version':'1','icons':[{'src':'x','theme':'blue'}]},'$.params.clientInfo.icons[0].theme'),
                           ('capabilities',{'roots':{'listChanged':1}},'$.params.capabilities.roots.listChanged'),
                           ('capabilities',{'sampling':{'tools':[]}},'$.params.capabilities.sampling.tools'),
                           ('capabilities',{'experimental':{'vendor/tool':[]}},'$.params.capabilities.experimental["vendor/tool"]'),
                           ('capabilities',{'elicitation':{'form':{'schemaValidation':'yes'}}},'$.params.capabilities.elicitation.form.schemaValidation'),
                           ('_meta',[],'$.params._meta')]:
        params=copy.deepcopy(PARAMS);params[key]=value;cases.append((params,path))
    for key in ['protocolVersion','capabilities','clientInfo']:
        params=copy.deepcopy(PARAMS);params.pop(key);cases.append((params,'$.params.'+key))
    for key,value in [('name',None),('version',None),('title',1),('description',[]),('websiteUrl',False),('icons',True),
                      ('icons',[None]),('icons',[{}]),('icons',[{'src':'x','sizes':[1]}]),('icons',[{'src':'x','mimeType':True}])]:
        params=copy.deepcopy(PARAMS);params['clientInfo'][key]=value
        location='$.params.clientInfo.'+key
        if key=='icons' and isinstance(value,list):
            location+='[0]'
            if value==[{}]:location+='.src'
            elif isinstance(value[0],dict):location+='.sizes[0]' if 'sizes' in value[0] else '.mimeType'
        cases.append((params,location))
    for value,path in [({'extensions':{'vendor/api':None}},'$.params.capabilities.extensions["vendor/api"]'),
                       ({'roots':[]},'$.params.capabilities.roots'),({'sampling':False},'$.params.capabilities.sampling'),
                       ({'sampling':{'context':False}},'$.params.capabilities.sampling.context'),
                       ({'elicitation':{'url':1}},'$.params.capabilities.elicitation.url')]:
        params=copy.deepcopy(PARAMS);params['capabilities']=value;cases.append((params,path))
    return cases


class ProtocolPreflight(unittest.TestCase):
    def test_invalid_initialization_never_installs_in_any_standalone_skill(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);observer=root/'observer.py';observer.write_text(OBSERVER)
            for scripts in sorted((ROOT/'skills').glob('*/scripts')):
                for params,path in invalid_initializations():
                    with self.subTest(skill=scripts.parent.name,path=path):
                        counts=root/'counts.json';request={'jsonrpc':'2.0','id':1,'method':'initialize','params':params}
                        result=subprocess.run([sys.executable,'-I','-B',str(observer),str(scripts/'cli.py'),str(counts),'--runtime-home',str(root/'runtime'),'--','mcp'],input=json.dumps(request)+'\n',capture_output=True,text=True,timeout=20)
                        self.assertEqual(json.loads(counts.read_text()),{'install':0,'session':0},result.stderr[-500:])
                        self.assertEqual(result.returncode,1,result.stderr[-500:]);detail=json.loads(result.stdout)['error']['data']
                        self.assertEqual(detail['fieldPath'],path);self.assertEqual(detail['outcome'],'not_executed')
                        self.assertEqual(detail['phase'],'validation');self.assertFalse(detail['retryable']);self.assertFalse(detail['replayAllowed'])
                        self.assertFalse((root/'runtime').exists())

    def test_known_optional_types_and_legacy_extension_metadata_are_preserved(self):
        stream=load('mcp_stream')
        params=copy.deepcopy(PARAMS)
        params.update(_meta={'progressToken':'作业','vendor/data':{'free':[1,True]}},futureClientField={'any':True})
        params['capabilities']={'experimental':{'vendor/feature':{'options':[True]}},'extensions':{'vendor/extension':{}},'roots':{'listChanged':None},'sampling':{'tools':{},'context':None},'elicitation':{'form':{'schemaValidation':True},'url':{}},'futureCapability':[]}
        params['clientInfo'].update(title=None,description='文档',websiteUrl='https://example.invalid',icons=[{'src':'data:image/png;base64,AA==','mimeType':'image/png','sizes':['any','32x32'],'theme':'dark','futureIcon':[]}],futureImplementationField={})
        for protocol in ['2024-11-05','2025-11-25','2026-07-28','future-version','']:
            params['protocolVersion']=protocol;request={'jsonrpc':'2.0','id':'init','method':'initialize','params':params}
            self.assertEqual(stream.preflight(json.dumps(request)),request)
        request={'jsonrpc':'2.0','id':'metadata','method':'tools/list','params':{'_meta':{'io.modelcontextprotocol/protocolVersion':'2026-07-28','io.modelcontextprotocol/clientCapabilities':{}}}}
        self.assertEqual(stream.preflight(json.dumps(request)),request)
        for path,value in [('title',1),('icons','x'),('websiteUrl',True)]:
            params=copy.deepcopy(PARAMS);params['clientInfo'][path]=value
            with self.subTest(path=path),self.assertRaisesRegex(ValueError,re.escape('$.params.clientInfo.'+path)):
                stream.preflight(json.dumps({'jsonrpc':'2.0','id':1,'method':'initialize','params':params}))

    def test_stream_wire_preserves_native_utf8_size_and_roundtrip(self):
        stream=load('mcp_stream');message={'id':'汉'*180000+'😀','method':'methods'}
        class Process:
            stdin=io.BytesIO()
        wire=object.__new__(stream.Wire);wire.process=Process();wire.send(message)
        encoded=wire.process.stdin.getvalue()
        self.assertLessEqual(len(encoded),1<<20)
        self.assertEqual(json.loads(encoded),message)
        self.assertEqual(encoded.count(b'\n'),1)

    def test_invalid_unicode_strings_and_keys_have_paths_before_install(self):
        parse=load('strict_json').loads
        for raw,path in [(r'{"operations":[{"params":{"text":"\ud800"}}]}','$.operations[0].params.text'),
                         (r'{"x":["\udc00"]}','$.x[0]'),
                         (r'{"x":{"bad\ud800":0}}',r'$.x["bad\ud800"]')]:
            with self.subTest(raw=raw),self.assertRaisesRegex(ValueError,re.escape(path)):
                parse(raw)
        self.assertEqual(parse(r'{"text":"\ud83d\ude00中文"}'),{'text':'😀中文'})

    def test_structured_json_error_path_does_not_split_quoted_key_text(self):
        parse=load('strict_json').loads;errors=load('operation_errors')
        for raw,path in [(r'{"bad expected name":0,"bad expected name":1}','$["bad expected name"]'),
                         (r'{"bad => name":NaN}','$["bad => name"]')]:
            try:parse(raw)
            except ValueError as error:self.assertEqual(errors.describe(error)['fieldPath'],path)
            else:self.fail('invalid JSON accepted')

    def test_escaped_surrogates_are_rejected_before_install_in_public_editing_entries(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);observer=root/'observer.py';observer.write_text(OBSERVER);plan=root/'plan.json'
            for scripts in sorted((ROOT/'skills').glob('*/scripts')):
                for entry,raw,path in [('mcp',r'{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"doc_new","arguments":{"name":"\ud800"}}}','$.params.arguments.name'),
                                       ('serve',r'{"id":1,"method":"doc.new","params":{"name":"\udc00"}}','$.params.name'),
                                       ('workflow',r'{"document":{"width":16,"height":16},"operations":[{"command":"type.create","params":{"text":"\ud800"}}]}','$.operations[0].params.text'),
                                       ('commands',r'{"schema":"craft-command-plan/v1","operations":[{"tool":"doc_new","params":{"name":"\ud800"}}]}','$.operations[0].params.name'),
                                       ('desktop',r'{"schema":"craft-command-plan/v1","operations":[{"tool":"doc_new","params":{"name":"\ud800"}}]}','$.operations[0].params.name')]:
                    with self.subTest(skill=scripts.parent.name,entry=entry):
                        counts=root/'counts.json';flags=['--runtime-home',str(root/'runtime')]
                        if entry in {'mcp','serve'}:
                            script=scripts/'cli.py';flags+=['--',entry];input=raw+'\n'
                        else:
                            plan.write_text(raw);script=scripts/(entry+'.py');flags=(['run'] if entry in {'commands','desktop'} else [])+[str(plan),'--output',str(root/'output'),*flags];input=''
                        result=subprocess.run([sys.executable,'-I','-B',str(observer),str(script),str(counts),*flags],input=input,capture_output=True,text=True,timeout=20)
                        self.assertEqual(json.loads(counts.read_text()),{'install':0,'session':0},result.stderr[-500:])
                        self.assertEqual(result.returncode,1,result.stdout[-500:]+result.stderr[-500:]);reply=json.loads(result.stdout)
                        detail=reply['error']['data'] if entry=='mcp' else reply['errorData'] if entry=='serve' else reply
                        self.assertEqual(detail['fieldPath'],path);self.assertEqual(detail['outcome'],'not_executed');self.assertFalse(detail['retryable'])
                        self.assertFalse((root/'runtime').exists());self.assertFalse((root/'output').exists())


@unittest.skipUnless(os.environ.get('CRAFT_NATIVE_COMMANDS')=='1','requires pinned native runtime')
class NativeWireBoundary(unittest.TestCase):
    def test_large_unicode_id_keeps_one_native_serve_process_and_saves(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);observer=root/'observer.py';observer.write_text(NATIVE_OBSERVER);counts=root/'counts.json'
            identifier='汉'*180000+'😀'
            requests=[{'id':identifier,'method':'methods'}, {'id':'new','method':'doc.new','params':{'width':16,'height':16}}, {'id':'save','method':'doc.save','params':{'path':'saved.pcraft'}}, {'id':'open','method':'doc.open','params':{'path':'saved.pcraft'}}, {'id':'inspect','method':'doc.inspect'}]
            text=''.join(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n' for row in requests)
            self.assertLess(len(text.encode()),1<<20)
            result=subprocess.run([sys.executable,'-I','-B',str(observer),str(SCRIPTS/'cli.py'),str(counts),'--runtime-home',os.environ['CRAFT_RUNTIME_HOME'],'--','serve','--automation-read-root',str(root),'--automation-write-root',str(root)],input=text,capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stdout[-500:]+result.stderr[-500:])
            replies=[json.loads(line) for line in result.stdout.splitlines()]
            self.assertEqual([row['id'] for row in replies],[identifier,'new','save','open','inspect'])
            self.assertTrue(all(row['ok'] for row in replies));self.assertTrue((root/'saved.pcraft').is_file())
            self.assertEqual(json.loads(counts.read_text()),{'started':1,'stopped':True})
            record({'mode':'serve-stdio','status':'PASS','utf8IdBytes':len(identifier.encode()),'inputBytes':len(text.encode()),'operations':5,'nativeProcesses':1,'stopped':True,'savedReopened':True,'savedSha256':hashlib.sha256((root/'saved.pcraft').read_bytes()).hexdigest()})

    def test_extended_initialize_and_metadata_only_native_modes_save_in_one_process(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);observer=root/'observer.py';observer.write_text(NATIVE_OBSERVER)
            for mode in ['legacy-extensions','metadata-only']:
                counts=root/(mode+'-counts.json');saved=mode+'.pcraft';params=copy.deepcopy(PARAMS)
                params['protocolVersion']='future-version';params['_meta']={'vendor/data':{'free':[1,True]}}
                params['capabilities']={'extensions':{'vendor/tool':{}},'futureCapability':[]}
                params['clientInfo'].update(title=None,icons=[{'src':'data:image/png;base64,AA==','sizes':['any'],'theme':'dark'}],futureField={})
                meta={'io.modelcontextprotocol/protocolVersion':'2026-07-28','io.modelcontextprotocol/clientCapabilities':{}}
                messages=[]
                if mode=='legacy-extensions':
                    messages=[{'jsonrpc':'2.0','id':'init','method':'initialize','params':params},{'jsonrpc':'2.0','method':'notifications/initialized'}]
                messages.append({'jsonrpc':'2.0','id':'list','method':'tools/list','params':{'_meta':meta} if mode=='metadata-only' else None})
                for index,(name,args) in enumerate([('doc_new',{'width':16,'height':16,'name':'中文😀'}),('doc_save',{'path':saved}),('doc_open',{'path':saved}),('doc_inspect',{})],1):
                    tools={'name':name,'arguments':args}
                    if mode=='metadata-only':tools['_meta']=meta
                    messages.append({'jsonrpc':'2.0','id':index,'method':'tools/call','params':tools})
                result=subprocess.run([sys.executable,'-I','-B',str(observer),str(SCRIPTS/'cli.py'),str(counts),'--runtime-home',os.environ['CRAFT_RUNTIME_HOME'],'--','mcp','--automation-read-root',str(root),'--automation-write-root',str(root)],input=''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in messages),capture_output=True,text=True,timeout=30)
                with self.subTest(mode=mode):
                    self.assertEqual(result.returncode,0,result.stdout[-1000:]+result.stderr[-500:])
                    replies=[json.loads(line) for line in result.stdout.splitlines()]
                    self.assertEqual(len(replies),6 if mode=='legacy-extensions' else 5)
                    self.assertTrue(all('result' in row for row in replies));self.assertTrue((root/saved).is_file())
                    self.assertEqual(json.loads(counts.read_text()),{'started':1,'stopped':True})
                    record({'mode':mode,'status':'PASS','operations':len(messages),'nativeProcesses':1,'stopped':True,'savedReopened':True,'savedSha256':hashlib.sha256((root/saved).read_bytes()).hexdigest()})


def record(case):
    target=os.environ.get('CRAFT_WIRE_BOUNDARY_REPORT')
    if not target:return
    path=Path(target);value=json.loads(path.read_text()) if path.exists() else {'status':'PASS','scope':'Actual pinned native; each healthy stream has one process; no GUI','cases':[]}
    value['cases'].append(case);path.write_text(json.dumps(value,indent=2)+'\n')


if __name__=='__main__':
    unittest.main()
