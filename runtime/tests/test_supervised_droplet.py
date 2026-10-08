"""Droplet 原生引擎保存语义与逐文件确认边界。"""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[2];BINARY=os.environ.get('CRAFT_SUPERVISED_BINARY')
spec=importlib.util.spec_from_file_location('droplet_supervisor_test',ROOT/'skills/photocraft-use/scripts/cli_supervisor.py')
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)

class DropletPreflight(unittest.TestCase):
    def test_invalid_plan_never_queries_scans_or_launches(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'bad.pcdroplet';p.write_text('{"photocraftDroplet":1,"action":{"steps":[["layer.new.layer",{"name":"A","name":"B"}]]}}')
            with mock.patch.object(s.subprocess,'run') as query,mock.patch.object(s.subprocess,'Popen') as launch,mock.patch.object(s.os,'scandir') as scan:
                with self.assertRaises(ValueError):s.execute('unused',['droplet',str(p),temp],io.StringIO())
                query.assert_not_called();launch.assert_not_called();scan.assert_not_called()

    def test_plan_uses_engine_ascii_case_and_backslash_stem_without_writing(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);source=root/'prefix\\name.pcraft';source.write_bytes(b'not opened during planning')
            p=root/'plan.pcdroplet';p.write_text(json.dumps({'photocraftDroplet':1,'action':{'steps':[]},'options':{'format':'.Ä','quality':True,'suffix':'ignored'}}))
            output=str(root/'out')+'/'
            events,checks,lines=s.droplet_plan(['droplet',str(p),str(source),'--out',output])
            self.assertEqual(checks[1]['files'],[{'input':str(source),'target':output+'name.Ä'}])
            self.assertEqual(events[2],('doc_save',{'path':output+'name.Ä'},False))
            self.assertFalse((root/'out').exists())

@unittest.skipUnless(BINARY,'explicit native candidate required')
class NativeDroplet(unittest.TestCase):
    def prepare(self,root,steps=None,options=None):
        inputs=root/'inputs';inputs.mkdir()
        for name in ['b.pcraft','a.pcraft']:
            r=subprocess.run([BINARY,'run','--new={"width":32,"height":24}','--cmd=layer.new.layer','--params={"name":"Source"}','--out',str(inputs/name)],capture_output=True,text=True,timeout=30)
            self.assertEqual(r.returncode,0,r.stderr)
        p=root/'test.pcdroplet';p.write_text(json.dumps({'photocraftDroplet':1,'name':'保留旧格式','action':{'steps':steps if steps is not None else [['layer.new.layer',{'name':'Droplet'}]]},'options':options or {}}))
        output=root/'output';return inputs,output,['droplet',str(p),str(inputs),'--out',str(output)]

    def test_unconfirmed_plan_never_opens_or_saves(self):
        with tempfile.TemporaryDirectory() as t:
            _,output,argv=self.prepare(Path(t))
            r=subprocess.run([BINARY,'droplet','--supervised',*argv[1:]],input='',capture_output=True,text=True,timeout=30)
            self.assertNotEqual(r.returncode,0,'old droplet ignored supervision and saved without confirmation')
            self.assertFalse(output.exists())
            self.assertEqual([json.loads(x)['tool'] for x in r.stdout.splitlines()],['droplet_plan'])

    def test_healthy_fresh_sessions_legacy_stdout_and_layers(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);inputs,output,argv=self.prepare(root);before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs.iterdir()};text=io.StringIO()
            r=s.execute(BINARY,argv,text)
            self.assertEqual(r['result'],'PASS');self.assertEqual(text.getvalue(),''.join('ok    '+str(output/n)+'\n' for n in ['a.pcraft','b.pcraft']))
            self.assertEqual([x['tool'] for x in r['receipts']],['droplet_plan','doc_open','command_run','doc_save','doc_open','command_run','doc_save','droplet_complete'])
            for name in ['a.pcraft','b.pcraft']:
                info=subprocess.run([BINARY,'info',str(output/name)],capture_output=True,text=True,timeout=30)
                self.assertEqual(info.returncode,0,info.stderr);self.assertEqual([x['name'] for x in json.loads(info.stdout)['layers']],['Droplet','Source','Background'])
            self.assertEqual(before,{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs.iterdir()})

    def test_preserves_string_tuple_object_actions_and_input_order_duplicates(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);inputs,output,argv=self.prepare(root,steps=['select.all',['layer.new.layer',{'name':'Tuple'},'ignored'],{'id':'layer.new.layer','params':{'name':'Object'},'metadata':'ignored'}])
            argv=['droplet',argv[1],str(inputs/'b.pcraft'),str(inputs/'a.pcraft'),str(inputs/'b.pcraft'),'--out',str(output)]
            text=io.StringIO();r=s.execute(BINARY,argv,text)
            self.assertEqual([x['arguments']['path'] for x in r['receipts'] if x['tool']=='doc_open'],[str(inputs/n) for n in ['b.pcraft','a.pcraft','b.pcraft']])
            info=subprocess.run([BINARY,'info',str(output/'a.pcraft')],capture_output=True,text=True,timeout=30)
            self.assertEqual([x['name'] for x in json.loads(info.stdout)['layers']],['Object','Tuple','Source','Background'])

    def test_default_output_options_override_quality_and_pixels_match_legacy(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);inputs,output,argv=self.prepare(root,steps=['image.imageRotation.90cw'],options={'format':'.JPG','quality':6,'output':str(root/'from-options'),'suffix':'ignored','overrideOpen':True})
            public=Path.home()/'.local/share/craft-runtimes/photocraft/0.2.0-craft.1/photocraft-cli'
            self.assertTrue(public.is_file())
            original=[str(public),'droplet',argv[1],str(inputs),'--out',str(root/'legacy')]
            legacy=subprocess.run(original,capture_output=True,text=True,timeout=30);self.assertEqual(legacy.returncode,0,legacy.stderr)
            text=io.StringIO();r=s.execute(BINARY,argv,text)
            for n in ['a.jpg','b.jpg']:
                self.assertEqual((output/n).read_bytes(),(root/'legacy'/n).read_bytes())
                with Image.open(output/n) as im:self.assertEqual(im.size,(24,32))
            self.assertEqual([x['arguments']['quality'] for x in r['receipts'] if x['tool']=='doc_save'],[6.0,6.0])
            s.execute(BINARY,['droplet',argv[1],str(inputs/'a.pcraft')],io.StringIO());self.assertTrue((root/'from-options/a.jpg').exists())
            v=json.loads(Path(argv[1]).read_text());v['options']={};Path(argv[1]).write_text(json.dumps(v))
            s.execute(BINARY,['droplet',argv[1],str(inputs/'a.pcraft')],io.StringIO());self.assertTrue((inputs/'droplet-output/a.pcraft').exists())


    def test_changed_quality_is_rejected_before_open_actions_and_save(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);_,output,argv=self.prepare(root,options={'quality':6});original=s.subprocess.run
            def query(args,*a,**kw):
                r=original(args,*a,**kw)
                if args[1:]==['--supervision-info']:
                    path=Path(argv[1]);value=json.loads(path.read_text());value['options']['quality']=12;path.write_text(json.dumps(value))
                return r
            log=root/'quality-events.jsonl'
            with mock.patch.dict(os.environ,CRAFT_SUPERVISED_LOG=str(log)),mock.patch.object(s.subprocess,'run',side_effect=query):
                with self.assertRaises(Exception) as caught:s.execute(ROOT/'runtime/tests/fixtures/supervised_proxy.py',argv,io.StringIO())
            self.assertFalse(output.exists(),'changed quality was used to save before plan refusal')
            self.assertEqual(caught.exception.outcome,'unknown');self.assertEqual(caught.exception.receipts,[])
            self.assertEqual(caught.exception.lastAttempt['sequence'],1)
            rows=[json.loads(x) for x in log.read_text().splitlines()]
            self.assertEqual([x['nativeEvent']['sequence'] for x in rows if 'nativeEvent' in x],[1])
            self.assertFalse(any('confirmation' in x for x in rows))

    def test_plan_mismatch_never_creates_output(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);_,output,argv=self.prepare(root);log=root/'events.jsonl'
            with mock.patch.dict(os.environ,CRAFT_SUPERVISED_LOG=str(log),CRAFT_SUPERVISED_FAULT='wrong-plan',CRAFT_SUPERVISED_AT='1'):
                with self.assertRaises(Exception) as caught:s.execute(ROOT/'runtime/tests/fixtures/supervised_proxy.py',argv,io.StringIO())
            self.assertEqual(caught.exception.outcome,'unknown');self.assertFalse(output.exists());self.assertEqual(caught.exception.receipts,[])
            self.assertFalse(any('confirmation' in json.loads(x) for x in log.read_text().splitlines()))

    def test_post_save_faults_stop_next_file_preserve_reopen_and_never_replay(self):
        for fault in ['duplicate','nonfinite','semantic','save-array','wrong-save-path','extra-frame']:
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as t:
                root=Path(t);inputs,output,argv=self.prepare(root);before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs.iterdir()};log=root/'events.jsonl';text=io.StringIO()
                with mock.patch.dict(os.environ,CRAFT_SUPERVISED_LOG=str(log),CRAFT_SUPERVISED_FAULT=fault,CRAFT_SUPERVISED_AT='4'):
                    with self.assertRaises(Exception) as caught:s.execute(ROOT/'runtime/tests/fixtures/supervised_proxy.py',argv,text)
                self.assertEqual(caught.exception.outcome,'failed' if fault=='semantic' else 'unknown');self.assertFalse(caught.exception.retryable);self.assertEqual(len(caught.exception.receipts),3);self.assertEqual(caught.exception.lastAttempt['sequence'],4)
                self.assertEqual(text.getvalue(),'');self.assertFalse((output/'b.pcraft').exists())
                saved=output/'a.pcraft';digest=hashlib.sha256(saved.read_bytes()).hexdigest();info=subprocess.run([BINARY,'info',str(saved)],capture_output=True,text=True,timeout=30)
                self.assertEqual(info.returncode,0,info.stderr);self.assertEqual([x['name'] for x in json.loads(info.stdout)['layers']],['Droplet','Source','Background']);self.assertEqual(digest,hashlib.sha256(saved.read_bytes()).hexdigest())
                self.assertEqual(before,{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs.iterdir()});rows=[json.loads(x) for x in log.read_text().splitlines()]
                self.assertEqual([x['confirmation'] for x in rows if 'confirmation' in x],['continue 1\n','continue 2\n','continue 3\n'])
                self.assertEqual([x['nativeEvent']['sequence'] for x in rows if 'nativeEvent' in x],[1,2,3,4])

    def test_native_failure_stops_supervision_and_ordinary_droplet_still_continues(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);inputs,output,argv=self.prepare(root);(inputs/'a.pcraft').write_bytes(b'invalid')
            with self.assertRaises(Exception) as caught:s.execute(BINARY,argv,io.StringIO())
            self.assertEqual(caught.exception.outcome,'failed');self.assertEqual(len(caught.exception.receipts),1);self.assertFalse(output.exists())
            ordinary=subprocess.run([BINARY,*argv],capture_output=True,text=True,timeout=30)
            self.assertNotEqual(ordinary.returncode,0);self.assertTrue((output/'b.pcraft').exists());self.assertIn('ok    '+str(output/'b.pcraft'),ordinary.stdout)

if __name__=='__main__':unittest.main()
