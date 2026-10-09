"""流式入口启动配置须在读取请求、安装及启动会话之前拒绝。"""
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_native_cli_preflight import OBSERVER

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/photocraft-use/scripts'

NATIVE_OBSERVER = '''import json,runpy,subprocess,sys
from pathlib import Path
script,counts,*args=sys.argv[1:];children=[];original=subprocess.Popen
def observe(*args,**kwargs):
 child=original(*args,**kwargs);children.append(child);return child
subprocess.Popen=observe;sys.argv=[script,*args]
try:runpy.run_path(script,run_name='__main__')
finally:Path(counts).write_text(json.dumps({'started':len(children),'stopped':all(child.poll() is not None for child in children)}))
'''


def load(name):
    spec = importlib.util.spec_from_file_location('launch_test_' + name, SCRIPTS / (name + '.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


class StreamLaunchPreflight(unittest.TestCase):
    def test_invalid_roots_and_missing_values_are_rejected_before_install(self):
        for scripts in sorted((ROOT/'skills').glob('*/scripts')):
            with self.subTest(skill=scripts.parent.name):
                self.check_invalid_launch(scripts)

    def check_invalid_launch(self, scripts):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); observer = root / 'observer.py'; observer.write_text(OBSERVER)
            token = root / 'token'; token.write_text('sensitive invalid token')
            before = token.read_bytes()
            for mode in ['mcp', 'serve']:
                cases = [(['--automation-read-root', str(root / 'absent')], '$argv[2]'),
                         (['--automation-write-root=' + str(token)], '$argv[1]'),
                         (['--automation-read-root='], '$argv[1]'),
                         (['--automation-write-root'], '$argv[1]'),
                         (['--quality'], '$argv[1]')]
                if mode == 'mcp':
                    cases += [(['--bridge=192.168.3.100:1', '--control-token=' + 'a'*64], '$argv[1]'),
                              (['--bridge=127.0.0.1:1'], '$argv'),
                              (['--bridge=127.0.0.1:1', '--control-token=secret'], '$argv[2]'),
                              (['--bridge=127.0.0.1:1', '--control-token-file=' + str(token)], '$argv[2]'),
                              (['--bridge=127.0.0.1:1', '--control-token-file=' + str(root/'missing-token')], '$argv[2]'),
                              (['--bridge=127.0.0.1:1', '--control-token=' + 'b'*64, '--control-token-file=' + str(token)], '$argv[3]')]
                request = {'jsonrpc':'2.0','id':1,'method':'tools/list'} if mode == 'mcp' else {'id':1,'method':'methods'}
                for index, (flags, path) in enumerate(cases):
                    with self.subTest(mode=mode, flags=flags):
                        counts = root / 'counts.json'
                        env = {key:value for key,value in os.environ.items() if key not in {'PHOTOCRAFT_CONTROL_TOKEN','PHOTOCRAFT_CONTROL_TOKEN_FILE'}}
                        result = subprocess.run([sys.executable,'-I','-B',str(observer),str(scripts/'cli.py'),str(counts),'--runtime-home',str(root/'runtime'),'--',mode,*flags],input=json.dumps(request)+'\n',capture_output=True,text=True,env=env,timeout=20)
                        self.assertEqual(json.loads(counts.read_text()), {'install':0,'session':0}, result.stdout+result.stderr)
                        self.assertEqual(result.returncode, 1, result.stdout+result.stderr)
                        reply = json.loads(result.stdout)
                        detail = reply['error']['data'] if mode == 'mcp' else reply['errorData']
                        self.assertEqual(detail['fieldPath'], path)
                        self.assertEqual(detail['phase'], 'validation')
                        self.assertEqual(detail['outcome'], 'not_executed')
                        self.assertFalse(detail['retryable']); self.assertFalse(detail['replayAllowed'])
                        self.assertNotIn('sensitive invalid token',result.stdout+result.stderr)
                        self.assertNotIn('secret',result.stdout+result.stderr)
                        self.assertFalse((root/'runtime').exists())
                        self.assertFalse((root/'missing-token').exists())
                        self.assertEqual(token.read_bytes(), before)

    def test_invalid_configuration_does_not_consume_the_input_iterator(self):
        class Input:
            def __iter__(self):
                raise AssertionError('invalid startup must not read input')
        for mode in ['mcp', 'serve']:
            stream = load(mode + '_stream'); output = io.StringIO()
            with self.subTest(mode=mode):
                code = stream.run([mode,'--automation-read-root='], lambda: self.fail('installed'), Input(), output)
                self.assertEqual(code, 1)

    def test_native_option_order_ignored_options_and_inactive_configuration_are_preserved(self):
        launch = load('stream_launch')
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {}, clear=True):
            root = Path(temporary); token = root/'token'; token.write_text('A'*64+'\n')
            (root/'link').symlink_to(root, target_is_directory=True)
            for mode in ['mcp','serve']:
                for flags in [[],['--help','-h','ignored','--unused=value'],
                              ['--automation-read-root=bad','--automation-read-root',str(root/'link')],
                              ['--automation-write-root',str(root),'--control-token=inactive-invalid'],
                              ['--quality=ignored','--automation-read-root=.']]:
                    with self.subTest(mode=mode,flags=flags):launch.preflight([mode,*flags])
            for host in ['127.0.0.1','localhost','[::1]','::1']:
                launch.preflight(['mcp','--bridge='+host+':1234','--control-token-file',str(token),'--automation-read-root=inactive-missing'])
            with patch.dict(os.environ, {'PHOTOCRAFT_CONTROL_TOKEN':'B'*64}):
                launch.preflight(['mcp','--bridge=localhost:1'])
                launch.preflight(['mcp','--bridge=localhost:1','--control-token='+'C'*64])
            with patch.dict(os.environ, {'PHOTOCRAFT_CONTROL_TOKEN_FILE':str(token)}):
                launch.preflight(['mcp','--bridge=localhost:1'])
                with self.assertRaisesRegex(ValueError, 'control_token_conflict'):
                    launch.preflight(['mcp','--bridge=localhost:1','--control-token='+'D'*64])

    @unittest.skipUnless(os.environ.get('CRAFT_NATIVE_COMMANDS') == '1', 'requires pinned native runtime')
    def test_real_native_modes_keep_shared_documents_with_legacy_launch_options(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            observer = root/'native-observer.py'; observer.write_text(NATIVE_OBSERVER)
            # 每个协议只启动一次，连续完成创建、保存及检查；不启动桌面GUI。
            for mode in ['mcp','serve']:
                save = mode+'.pcraft'
                if mode == 'mcp':
                    requests = [{'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'launch-test','version':'1'}}},
                                {'jsonrpc':'2.0','method':'notifications/initialized'},
                                *[{'jsonrpc':'2.0','id':index,'method':'tools/call','params':{'name':name,'arguments':arguments}}
                                  for index,(name,arguments) in enumerate([('doc_new',{'width':32,'height':32}),('doc_save',{'path':save}),('doc_inspect',{})],2)]]
                else:
                    requests = [{'id':index,'method':name,'params':arguments} for index,(name,arguments) in enumerate([
                        ('doc.new',{'width':32,'height':32}),('doc.save',{'path':save}),('doc.inspect',{})],1)]
                counts = root/(mode+'-processes.json')
                argv = [sys.executable,'-I','-B',str(observer),str(SCRIPTS/'cli.py'),str(counts),'--runtime-home',os.environ['CRAFT_RUNTIME_HOME'],'--',mode,
                        '--automation-read-root=ignored-missing','--automation-read-root',str(root),
                        '--automation-write-root='+str(root),'--help','--quality=ignored','--control-token=inactive-invalid']
                result = subprocess.run(argv,input=''.join(json.dumps(request)+'\n' for request in requests),capture_output=True,text=True,timeout=30)
                with self.subTest(mode=mode):
                    self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                    replies = [json.loads(line) for line in result.stdout.splitlines()]
                    self.assertEqual(len(replies),4 if mode == 'mcp' else 3)
                    self.assertTrue(all('result' in reply for reply in replies))
                    self.assertTrue((root/save).is_file())
                    self.assertEqual(json.loads(counts.read_text()), {'started':1,'stopped':True})


if __name__ == '__main__':
    unittest.main()
