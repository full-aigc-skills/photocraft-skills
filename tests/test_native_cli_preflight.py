"""原生 argv 的离线预检必须先于安装，保留原生合法动作表示。"""
import importlib.util
import json
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/photocraft-use/scripts'

# 观察而不修改独立技能；测试决不进行真实安装或启动原生进程。
OBSERVER = '''import importlib.util,json,runpy,subprocess,sys
from pathlib import Path
script,counts,*args=sys.argv[1:];calls={'install':0,'session':0}
def denied(key):
 def call(*a,**kw):calls[key]+=1;raise AssertionError('unexpected '+key)
 return call
subprocess.Popen=denied('session');original=importlib.util.spec_from_file_location
def observe(name,location,*a,**kw):
 spec=original(name,location,*a,**kw)
 if Path(location).name=='bootstrap.py':
  execute=spec.loader.exec_module
  def wrapped(module):execute(module);module.install=denied('install')
  spec.loader.exec_module=wrapped
 return spec
importlib.util.spec_from_file_location=observe;sys.argv=[script,*args]
try:runpy.run_path(script,run_name='__main__')
finally:Path(counts).write_text(json.dumps(calls))
'''


class NativeArgvPreflight(unittest.TestCase):
    def contract(self):
        spec = importlib.util.spec_from_file_location('native_cli_preflight_test', SCRIPTS/'cli_contract.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        return module

    def test_legacy_action_shapes_literal_json_and_option_forms_are_preserved(self):
        contract = self.contract()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            steps = [{'command':'layer.new.layer'}, {'id':'layer.new.layer', 'params':{'name':'Object'}, 'name':'recorded action metadata'}]
            for value in [steps, {'actions':steps, 'name':'Recorded'}]:
                file = root/'actions.json'; file.write_text(json.dumps(value))
                contract.preflight(['batch', '--actions='+str(file), '--in', str(root), '--out', str(root/'output')])
            droplet = root/'recipe.pcdroplet'
            droplet.write_text(json.dumps({'photocraftDroplet':1,'action':{'steps':['layer.new.layer',['layer.new.layer',{'name':'Tuple'},'ignored metadata'],*steps]}}))
            contract.preflight(['droplet',str(droplet),'source.pcraft'])
            contract.preflight(['run','--new={"width":32,"height":32}', '--cmd=type.create', '--params={"text":"literal $ref","features":{"$ref":"literal"}}', '--out=out.pcraft'])
            contract.preflight(['convert','in.pcraft','out.jpg','--quality=+010'])

    @unittest.skipUnless(os.environ.get('CRAFT_NATIVE_COMMANDS') == '1', 'requires pinned native runtime')
    def test_real_native_create_revision_batch_droplet_and_convert_keep_old_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve(); runtime = root/'runtime'; original = root/'source.pcraft'
            def run(*argv):
                result = subprocess.run([sys.executable,'-I','-B',str(SCRIPTS/'cli.py'),'--runtime-home',str(runtime),'--',*argv],capture_output=True,text=True,timeout=300)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                return result.stdout
            created = run('run','--new={"width":32,"height":32,"background":"white"}','--cmd=layer.new.layer','--params={"name":"Original"}','--out',str(original))
            receipt = json.loads(created); self.assertEqual(receipt['command'],'layer.new.layer')
            layer = receipt['result']['layer']; before = hashlib.sha256(original.read_bytes()).hexdigest()
            revised = root/'revision.pcraft'
            replies = run('run',str(original),'--cmd','layer.select','--params',json.dumps({'layer':layer}),'--cmd','layer.renameLayer','--params','{"name":"Revised"}','--out',str(revised)).splitlines()
            self.assertEqual([json.loads(line)['command'] for line in replies],['layer.select','layer.renameLayer'])
            self.assertTrue(any(row['name']=='Revised' for row in json.loads(run('info',str(revised)))['layers']))
            self.assertEqual(hashlib.sha256(original.read_bytes()).hexdigest(),before)
            image = root/'render.png'; self.assertEqual(run('convert',str(revised),str(image)),'')
            from PIL import Image
            with Image.open(image) as opened:self.assertEqual(opened.size,(32,32))
            inputs = root/'inputs'; inputs.mkdir(); (inputs/'source.pcraft').write_bytes(original.read_bytes())
            actions = root/'actions.json'; actions.write_text('{"actions":[{"command":"layer.new.layer","params":{"name":"Batch"}}]}')
            batch = root/'batch'
            self.assertIn('1 succeeded, 0 failed',run('batch','--actions',str(actions),'--in',str(inputs),'--out',str(batch)))
            self.assertTrue(any(row['name']=='Batch' for row in json.loads(run('info',str(batch/'source.pcraft')))['layers']))
            droplet = root/'recipe.pcdroplet'; droplet.write_text('{"photocraftDroplet":1,"action":{"name":"Recipe","steps":[["layer.new.layer",{"name":"Droplet"}]]},"options":{"format":"pcraft"}}')
            target = root/'droplet'; self.assertIn('ok',run('droplet',str(droplet),str(original),'--out',str(target)))
            self.assertTrue(any(row['name']=='Droplet' for row in json.loads(run('info',str(target/'source.pcraft')))['layers']))
            self.assertEqual(hashlib.sha256(original.read_bytes()).hexdigest(),before)

    def test_invalid_native_editing_arguments_never_install_or_start(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            wrapper = root / 'observer.py'; wrapper.write_text(OBSERVER)
            source = root / 'source.pcraft'; source.write_bytes(b'never opened fixture')
            actions = root / 'actions.json'; actions.write_text('[{"command":"layer.new.layer","params":{"name":"a","name":"b"}}]')
            droplet = root / 'bad.pcdroplet'; droplet.write_text('{"photocraftDroplet":1,"action":{"steps":[["layer.select",{"layer":true}]]}}')
            cases = [
                ['run', str(source), '--cmd', 'type.create', '--params', '{"text":"a","text":"b"}'],
                ['run', '--new', '{"width":32,"height":NaN}', '--out', str(root/'new.pcraft')],
                ['run', str(source), '--cmd', 'layer.select', '--params', '{"layer":1e999}'],
                ['run', str(source), '--cmd', 'layer.select', '--params', '[]'],
                ['run', str(source), '--cmd', 'layer.select', '--params', '{"layer":true}'],
                ['run', str(source), '--cmd', 'layer.new.layer', '--params', '{"typo":1}'],
                ['run', str(source), '--cmd', 'invented.command'],
                ['run', str(source), '--params', '{}'],
                ['run', str(source), '--cmd', 'layer.new.layer', '--fromat', 'png'],
                ['run', str(source), '--cmd=layer.select', '--params={"layer":{"$ref":"future.layer"}}'],
                ['convert', str(source), str(root/'new.png'), '--quality', '101'],
                ['batch', '--actions', str(actions), '--in', str(root), '--out', str(root/'batch')],
                ['droplet', str(droplet), str(source), '--out', str(root/'droplet')],
            ]
            for index, argv in enumerate(cases):
                with self.subTest(argv=argv):
                    counts = root / ('counts-'+str(index)+'.json')
                    result = subprocess.run([sys.executable, '-I', '-B', str(wrapper), str(SCRIPTS/'cli.py'), str(counts), '--runtime-home', str(root/'runtime'), '--', *argv], capture_output=True, text=True, timeout=20)
                    self.assertEqual(result.returncode, 1, result.stdout+result.stderr)
                    self.assertEqual(json.loads(counts.read_text()), {'install':0, 'session':0})
                    reply = json.loads(result.stdout)
                    self.assertEqual(reply['category'], 'validation_failed')
                    self.assertEqual(reply['phase'], 'validation')
                    self.assertEqual(reply['outcome'], 'not_executed')
                    self.assertFalse(reply['retryable'])
                    self.assertTrue(reply['fieldPath'].startswith('$'))
                    self.assertEqual(json.loads(counts.read_text()), {'install':0, 'session':0})
                    self.assertFalse((root/'runtime').exists())
                    self.assertFalse((root/'new.pcraft').exists())
                    self.assertFalse((root/'new.png').exists())
                    self.assertFalse((root/'batch').exists())
                    self.assertFalse((root/'droplet').exists())
                    self.assertEqual(source.read_bytes(), b'never opened fixture')


if __name__ == '__main__':
    unittest.main()
