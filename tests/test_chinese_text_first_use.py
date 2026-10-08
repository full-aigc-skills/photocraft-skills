"""固定宿主文字技能首次在线创建中文海报、定点修订与 PSD 交换。"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from test_native_workflow import product_fixture
ROOT=Path(__file__).resolve().parents[1]

@unittest.skipUnless(os.environ.get('CRAFT_CHINESE_TEXT_FIRST_USE')=='1','requires public native runtime and Pillow')
class ChineseTextFirstUseTests(unittest.TestCase):
 def test_single_text_skill_preserves_layers_and_pixels_during_chinese_revision(self):
  from PIL import Image,ImageChops
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary);skill=root/'.agents/skills/photocraft-cli-text'
   source=Path(os.environ.get('CRAFT_INSTALLED_TEXT_SKILL_ROOT',ROOT/'skills/photocraft-cli-text'))
   shutil.copytree(source,skill,ignore=shutil.ignore_patterns('__pycache__'))
   self.assertEqual([p.name for p in skill.parent.iterdir()],['photocraft-cli-text'])
   product=root/'product.png';product_fixture(product);original_product=hashlib.sha256(product.read_bytes()).hexdigest()
   plan=json.loads((skill/'examples/poster-plan.json').read_text())
   headline=next(op for op in plan['operations'] if op.get('as')=='headline');headline['params'].update(text='新品上市',font='Songti SC')
   workflow_python=os.environ.get('CRAFT_WORKFLOW_PYTHON',sys.executable)
   def execute(value,name,previous=None):
    path=root/(name+'.json');path.write_text(json.dumps(value,ensure_ascii=False))
    argv=[workflow_python,'-I','-B',str(skill/'scripts/workflow.py'),str(path),'--output',str(root/name),'--runtime-home',str(root/'fresh runtime'),'--asset','product='+str(product)]
    if previous:argv+=['--source',str(root/previous)]
    result=subprocess.run(argv,capture_output=True,text=True,env=dict(os.environ,PATH='/usr/bin:/bin'),timeout=240)
    return result
   first=execute(plan,'v1');self.assertEqual(first.returncode,0,first.stdout+first.stderr)
   manifest=json.loads(first.stdout);before=json.loads((root/'v1/native.json').read_text());layers={x['name']:x for x in before['layers']}
   self.assertEqual(layers['Headline']['text']['text'],'新品上市');self.assertEqual(len(layers),4)
   hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'v1').iterdir() if p.is_file()}
   revision={'expectedProjectSha256':manifest['files']['project.pcraft'],'minimumLayers':4,'operations':[{'command':'type.edit','params':{'layer':{'$ref':'headline.layer'},'text':'品牌焕新'}}],'exports':plan['exports']}
   second=execute(revision,'v2','v1');self.assertEqual(second.returncode,0,second.stdout+second.stderr)
   after=json.loads((root/'v2/native.json').read_text());changed={x['name']:x for x in after['layers']};self.assertEqual(changed['Headline']['text']['text'],'品牌焕新')
   self.assertEqual(changed['Headline']['id'],layers['Headline']['id'])
   self.assertEqual(changed['Headline']['text']['font'],'Songti SC')
   self.assertEqual(changed['Headline']['text']['sizePt'],layers['Headline']['text']['sizePt'])
   for name in ('Product','Caption'):
    self.assertEqual(changed[name],layers[name])
   psd=json.loads((root/'v2/psd-inspection.json').read_text());exchanged={x['name']:x for x in psd['layers']}
   self.assertEqual(exchanged['Headline']['text'],changed['Headline']['text'])
   self.assertEqual(exchanged['Headline']['text']['text'],'品牌焕新');self.assertEqual(exchanged['Headline']['kind'],'Type');self.assertEqual(len(exchanged),4)
   for name in ('Product','Caption'):
    for field in ('kind','visible','blend','hasMask','text'):self.assertEqual(exchanged[name].get(field),changed[name].get(field))
   with Image.open(root/'v1/design.png') as a,Image.open(root/'v2/design.png') as b:
    self.assertIsNotNone(ImageChops.difference(a.convert('RGB').crop((0,0,320,100)),b.convert('RGB').crop((0,0,320,100))).getbbox())
    self.assertEqual(a.convert('RGBA').crop((0,100,320,400)).tobytes(),b.convert('RGBA').crop((0,100,320,400)).tobytes())
   converted=subprocess.run([workflow_python,'-I','-B',str(skill/'scripts/cli.py'),'--runtime-home',str(root/'fresh runtime'),'--','convert',str(root/'v2/design.psd'),str(root/'psd-decoded.png')],capture_output=True,text=True,env=dict(os.environ,PATH='/usr/bin:/bin'),timeout=120)
   self.assertEqual(converted.returncode,0,converted.stdout+converted.stderr)
   with Image.open(root/'v2/design.png') as native,Image.open(root/'psd-decoded.png') as exchanged_image:self.assertEqual(native.convert('RGBA').tobytes(),exchanged_image.convert('RGBA').tobytes())
   for name,digest in hashes.items():self.assertEqual(hashlib.sha256((root/'v1'/name).read_bytes()).hexdigest(),digest)
   self.assertEqual(hashlib.sha256(product.read_bytes()).hexdigest(),original_product)
   bad=json.loads(json.dumps(revision));bad['operations'][0]['params']['layer']=999999999
   denied=execute(bad,'unknown-layer','v1');self.assertNotEqual(denied.returncode,0);self.assertFalse((root/'unknown-layer').exists())
   missing=json.loads(json.dumps(revision));missing['operations']=[{'command':'type.setStyle','params':{'layer':{'$ref':'headline.layer'},'font':'Craft Missing CJK Family 72625'}}]
   denied=execute(missing,'missing-font','v1');self.assertNotEqual(denied.returncode,0);self.assertIn('missing_fonts',denied.stdout+denied.stderr);self.assertFalse((root/'missing-font/manifest.json').exists());failure=json.loads((root/'missing-font/failure.json').read_text());self.assertFalse(failure['replayAllowed']);self.assertTrue((root/'missing-font'/failure['stage']).is_dir())
   self.assertFalse(any(skill.rglob('*.pyc')))
   evidence=os.environ.get('CRAFT_TEXT_EVIDENCE_DIR')
   if evidence:
    target=Path(evidence);target.mkdir(exist_ok=False)
    for name in ('v1','v2'):shutil.copytree(root/name,target/name)

if __name__=='__main__':unittest.main()
