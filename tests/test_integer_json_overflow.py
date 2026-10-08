"""超大整数字面量在任意深度及每个独立技能公开入口均先于安装拒绝。"""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

def load(name):
    path=ROOT/'skills/photocraft-use/scripts'/(name+'.py')
    spec=importlib.util.spec_from_file_location('integer_overflow_'+name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

class IntegerJSONOverflow(unittest.TestCase):
    def test_huge_integer_literals_are_refused_at_exact_paths_and_unknown_replies(self):
        parse=load('strict_json').loads
        for literal in ['1'+'0'*400,'-1'+'0'*400,'9'*5000,'-'+'9'*5000]:
            with self.subTest(length=len(literal),negative=literal.startswith('-')):
                with self.assertRaisesRegex(ValueError,r'nonfinite_json_value: \$\.items\[0\]\.quality'):
                    parse('{"items":[{"quality":'+literal+'}]}')
                with self.assertRaisesRegex(ValueError,r'\$\.result'):
                    load('mcp_session').strict_json(('{"result":'+literal+'}').encode())
                with self.assertRaises(Exception) as caught:
                    load('commands').parse_reply({'content':[{'type':'text','text':'{"result":'+literal+'}'}]})
                self.assertEqual(caught.exception.outcome,'unknown');self.assertFalse(caught.exception.retryable)

    def test_finite_large_integers_and_normal_numbers_keep_legacy_types(self):
        values=[0,1,-1,2**64,10**100,-10**100,1e308,-1e308,True,None]
        actual=load('strict_json').loads(json.dumps({'values':values}))['values']
        self.assertEqual(actual,values);self.assertEqual([type(v) for v in actual],[type(v) for v in values])

    def test_all_thirteen_public_skills_reject_before_install_session_and_output(self):
        helper=Path(__file__).with_name('test_native_cli_preflight.py')
        spec=importlib.util.spec_from_file_location('integer_preflight_observer',helper)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        scripts=sorted((ROOT/'skills').glob('*/scripts/cli.py'));self.assertEqual(len(scripts),13)
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);wrapper=root/'observer.py';wrapper.write_text(module.OBSERVER)
            source=root/'original.pcraft';source.write_bytes(b'original must not be opened')
            droplet=root/'overflow.pcdroplet'
            for script in scripts:
                for literal in ['1'+'0'*400,'-1'+'0'*400,'9'*5000,'-'+'9'*5000]:
                    with self.subTest(skill=script.parents[1].name,length=len(literal),negative=literal.startswith('-')):
                        droplet.write_text('{"photocraftDroplet":1,"action":{"steps":[]},"options":{"quality":'+literal+'}}')
                        counts=root/'counts.json';runtime=root/'runtime';output=root/'output'
                        result=subprocess.run([sys.executable,'-I','-B',str(wrapper),str(script),str(counts),'--runtime-home',str(runtime),'--','droplet',str(droplet),str(source),'--out',str(output)],capture_output=True,text=True,timeout=20)
                        self.assertEqual(result.returncode,1,result.stdout+result.stderr)
                        self.assertEqual(json.loads(counts.read_text()),{'install':0,'session':0})
                        reply=json.loads(result.stdout)
                        self.assertEqual(reply['category'],'validation_failed');self.assertEqual(reply['phase'],'validation');self.assertEqual(reply['outcome'],'not_executed')
                        self.assertFalse(reply['retryable']);self.assertEqual(reply['fieldPath'],'$argv[1].options.quality')
                        self.assertEqual(reply['code'],'nonfinite_json_value');self.assertEqual(reply['recoveryAction'],'correct_plan')
                        self.assertFalse(runtime.exists());self.assertFalse(output.exists());self.assertEqual(source.read_bytes(),b'original must not be opened')

if __name__=='__main__':unittest.main()
