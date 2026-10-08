"""原生 convert 保持原 files 保存语义，并在打开／保存回复之间确认。"""
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
spec=importlib.util.spec_from_file_location('convert_supervisor_candidate',ROOT/'skills/photocraft-use/scripts/cli_supervisor.py')
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)

@unittest.skipUnless(BINARY,'explicit native candidate required')
class NativeConvert(unittest.TestCase):
    def source(self,root):
        original=root/'original.pcraft'
        result=subprocess.run([BINARY,'run','--new={"width":32,"height":24}','--cmd=layer.new.layer','--params={"name":"Original"}','--out',str(original)],capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        return original

    def test_open_requires_confirmation_before_saving(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);original=self.source(root);output=root/'never.png'
            result=subprocess.run([BINARY,'convert','--supervised',str(original),str(output)],input='',capture_output=True,text=True,timeout=30)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual([json.loads(line)['tool'] for line in result.stdout.splitlines()],['doc_open'])
            self.assertFalse(output.exists())

    def test_healthy_native_psd_and_png_conversion_keeps_empty_stdout_and_source(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);original=self.source(root);before=hashlib.sha256(original.read_bytes()).hexdigest()
            for extension in ['pcraft','psd','png','jpg']:
                with self.subTest(extension=extension):
                    output=root/('converted.'+extension);text=io.StringIO()
                    result=s.execute(BINARY,['convert',str(original),str(output),'--quality=+010'],text)
                    self.assertEqual(result['result'],'PASS');self.assertEqual(text.getvalue(),'')
                    self.assertEqual([r['tool'] for r in result['receipts']],['doc_open','doc_save'])
                    self.assertEqual(hashlib.sha256(original.read_bytes()).hexdigest(),before)
                    if extension in ['pcraft','psd']:
                        info=subprocess.run([BINARY,'info',str(output)],capture_output=True,text=True,timeout=30)
                        self.assertEqual(info.returncode,0,info.stderr)
                        self.assertTrue(any(row['name']=='Original' for row in json.loads(info.stdout)['layers']))
                    else:
                        with Image.open(output) as image:self.assertEqual(image.size,(32,24))

    def test_explicit_format_precedence_and_legacy_pixels_are_preserved(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);original=self.source(root);legacy=root/'legacy.unknown';actual=root/'actual.unknown'
            result=subprocess.run([BINARY,'convert',str(original),str(legacy),'--format=png'],capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(result.stdout,'')
            text=io.StringIO();s.execute(BINARY,['convert',str(original),str(actual),'--format=png'],text)
            self.assertEqual(text.getvalue(),'')
            with Image.open(legacy) as a,Image.open(actual) as b:
                self.assertEqual(a.format,'PNG');self.assertEqual(b.format,'PNG');self.assertEqual(a.tobytes(),b.tobytes())

    def test_malformed_actual_open_never_saves(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);original=self.source(root);output=root/'never.png';log=root/'events.jsonl'
            with mock.patch.dict(os.environ,CRAFT_SUPERVISED_LOG=str(log),CRAFT_SUPERVISED_FAULT='duplicate',CRAFT_SUPERVISED_AT='1'):
                with self.assertRaises(Exception) as caught:s.execute(ROOT/'runtime/tests/fixtures/supervised_proxy.py',['convert',str(original),str(output)],io.StringIO())
            self.assertEqual(caught.exception.outcome,'unknown');self.assertEqual(caught.exception.receipts,[])
            self.assertFalse(output.exists())
            rows=[json.loads(line) for line in log.read_text().splitlines()]
            self.assertEqual([r['nativeEvent']['sequence'] for r in rows if 'nativeEvent' in r],[1])
            self.assertFalse(any('confirmation' in row for row in rows))

    def test_post_save_faults_preserve_original_and_reopen_saved_project_without_replay(self):
        for fault in ['duplicate','nonfinite','semantic','save-array','wrong-save-path','extra-frame']:
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary);original=self.source(root);output=root/'saved.pcraft';log=root/'events.jsonl'
                before=hashlib.sha256(original.read_bytes()).hexdigest()
                with mock.patch.dict(os.environ,CRAFT_SUPERVISED_LOG=str(log),CRAFT_SUPERVISED_FAULT=fault,CRAFT_SUPERVISED_AT='2'):
                    with self.assertRaises(Exception) as caught:s.execute(ROOT/'runtime/tests/fixtures/supervised_proxy.py',['convert',str(original),str(output)],io.StringIO())
                self.assertEqual(caught.exception.outcome,'failed' if fault=='semantic' else 'unknown')
                self.assertEqual(len(caught.exception.receipts),1);self.assertFalse(caught.exception.retryable)
                self.assertEqual(caught.exception.lastAttempt['sequence'],2)
                digest=hashlib.sha256(output.read_bytes()).hexdigest()
                info=subprocess.run([BINARY,'info',str(output)],capture_output=True,text=True,timeout=30)
                self.assertEqual(info.returncode,0,info.stderr)
                self.assertTrue(any(row['name']=='Original' for row in json.loads(info.stdout)['layers']))
                self.assertEqual(hashlib.sha256(output.read_bytes()).hexdigest(),digest)
                self.assertEqual(hashlib.sha256(original.read_bytes()).hexdigest(),before)
                rows=[json.loads(line) for line in log.read_text().splitlines()]
                self.assertEqual([r['confirmation'] for r in rows if 'confirmation' in r],['continue 1\n'])
                self.assertEqual([r['nativeEvent']['tool'] for r in rows if 'nativeEvent' in r],['doc_open','doc_save'])

    def test_known_save_failure_is_failed_and_never_claims_unexecuted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);original=self.source(root);output=root/'never.unknown'
            with self.assertRaises(Exception) as caught:s.execute(BINARY,['convert',str(original),str(output)],io.StringIO())
            self.assertEqual(caught.exception.outcome,'failed');self.assertEqual(caught.exception.phase,'reply_received')
            self.assertEqual(len(caught.exception.receipts),1);self.assertFalse(output.exists())

if __name__=='__main__':unittest.main()
