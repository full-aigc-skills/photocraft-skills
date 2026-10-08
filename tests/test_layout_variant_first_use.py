"""独立尺寸技能冷安装、真实图层重开和安全区拒绝。"""
import hashlib
import contextlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
ROOT=Path(__file__).resolve().parents[1]
@unittest.skipUnless(os.environ.get('CRAFT_LAYOUT_FIRST_USE')=='1','requires native online first use')
class LayoutFirstUse(unittest.TestCase):
 def test_canvas_and_resample_variants(self):
  retained=os.environ.get('CRAFT_LAYOUT_RETAINED_OUTPUT')
  if retained:
   target=Path(retained)
   if not target.is_absolute():raise ValueError('retained_output_absolute_required')
   target.mkdir(exist_ok=False);workspace=contextlib.nullcontext(str(target))
  else:workspace=tempfile.TemporaryDirectory(prefix='photo-layout-first-use-')
  with workspace as temp:
   root=Path(temp).resolve();skill=root/'only-resize'
   shutil.copytree(Path(os.environ.get('CRAFT_INSTALLED_RESIZE_SKILL_ROOT',ROOT/'skills/photocraft-cli-resize')),skill,ignore=shutil.ignore_patterns('__pycache__'))
   def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
   image=root/'product.png';image.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',120,160,8,6,0,0,0))+chunk(b'IDAT',zlib.compress((b'\0'+bytes([233,99,64,255])*120)*160))+chunk(b'IEND',b''))
   env={**os.environ,'PATH':'/usr/bin:/bin'};env.pop('CRAFT_RUNTIME_HOME',None)
   def run(plan,name,source=None):
    path=root/(name+'.json');path.write_text(json.dumps(plan));args=[sys.executable,'-I','-B',str(skill/'scripts/workflow.py'),str(path),'--output',str(root/name),'--runtime-home',str(root/'runtime')]
    if source:args.extend(['--source',str(source)])
    else:args.extend(['--asset','product='+str(image)])
    return subprocess.run(args,env=env,text=True,capture_output=True,timeout=180)
   def hashes(folder):return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir() if p.is_file()}
   failures={}
   def failed_delivery(name,code):
    target=root/name;self.assertFalse((target/'manifest.json').exists());self.assertFalse((target/'project.pcraft').exists())
    record=json.loads((target/'failure.json').read_text());self.assertEqual(record['schema'],'craft-failed-stage/v1');self.assertIn(code,record['error']);self.assertEqual(record['acceptance'],'not-a-successful-delivery');self.assertFalse(record['replayAllowed'])
    stage=(target/record['stage']).resolve();self.assertTrue(stage.is_relative_to(root));self.assertTrue((stage/'project.pcraft').is_file())
    for name,item in record['files'].items():self.assertEqual(hashlib.sha256((stage/name).read_bytes()).hexdigest(),item['sha256'])
    failures[target.name]=record
   source=root/'source';first=run(json.loads((skill/'examples/poster-plan.json').read_text()),'source');self.assertEqual(first.returncode,0,first.stdout+first.stderr)
   manifest=json.loads(first.stdout);original=hashes(source);native=json.loads((source/'native.json').read_text());bg=next(v['id'] for v in native['layers'] if v['name']=='Background')
   roles={'background':bg,'product':{'$ref':'product.layer'},'text':{'$ref':'headline.layer'}};observations={}
   for name,command,width,height in [('padding','image.canvasSize',360,440),('crop','image.canvasSize',300,380),('resample','image.imageSize',160,200)]:
    plan={'expectedProjectSha256':manifest['files']['project.pcraft'],'minimumLayers':4,'operations':[{'command':command,'params':{'width':width,'height':height,**({'anchor':'center','extensionColor':'transparent'} if command=='image.canvasSize' else {})}}],'exports':[{'format':'png'},{'format':'psd'}],'variant':{'width':width,'height':height,'safeArea':[8,8,width-16,height-16],'roles':roles}}
    result=run(plan,name,source);self.assertEqual(result.returncode,0,result.stdout+result.stderr)
    output=root/name;delivery=json.loads(result.stdout);report=json.loads((output/'layout-variant.json').read_text());saved=json.loads((output/'native.json').read_text());psd=json.loads((output/'psd-inspection.json').read_text())
    self.assertEqual(report['targetSize'],[width,height]);self.assertEqual([saved['width'],saved['height']],[width,height]);self.assertEqual(struct.unpack('>II',(output/'design.png').read_bytes()[16:24]),(width,height));self.assertEqual(len(saved['layers']),len(psd['layers']));self.assertEqual(delivery['layoutVariant']['sha256'],hashes(output)['layout-variant.json'])
    for role,entry in report['roles'].items():
     layer=next(v for v in psd['layers'] if v['name']==entry['name']);self.assertEqual(layer['kind'],entry['kind'])
     if role=='text':self.assertEqual(layer['text']['text'],'NOVA')
    self.assertEqual(original,hashes(source));observations[name]={'manifest':delivery,'layout':report}
    if name=='padding':
     checkpoint=run(plan,'source',source);self.assertEqual(checkpoint.returncode,1,checkpoint.stdout+checkpoint.stderr);self.assertIn('output_exists',checkpoint.stdout);self.assertEqual(original,hashes(source))
     bad=json.loads(json.dumps(plan));bad['variant']['safeArea']=[0,0,10,10];rejected=run(bad,'unsafe',source);self.assertEqual(rejected.returncode,1,rejected.stdout);self.assertIn('variant_safe_area_violation',rejected.stdout);failed_delivery('unsafe','variant_safe_area_violation')
     bad=json.loads(json.dumps(plan));bad['variant']['width']=361;rejected=run(bad,'mismatch',source);self.assertEqual(rejected.returncode,1,rejected.stdout);self.assertIn('variant_size_mismatch',rejected.stdout);failed_delivery('mismatch','variant_size_mismatch')
   self.assertEqual(original,hashes(source));self.assertFalse(list(skill.rglob('*.pyc')))
   if os.environ.get('CRAFT_LAYOUT_EVIDENCE_FILE'):
    with Path(os.environ['CRAFT_LAYOUT_EVIDENCE_FILE']).open('x') as file:json.dump({'schema':'photocraft-layout-first-use/v1','python':sys.version.split()[0],'sourceFiles':original,'variants':observations,'unsafeRejected':True,'sizeMismatchRejected':True,'allSourceFilesPreserved':True,'sourceOverwriteRejected':True,'failedDeliveries':failures,'retainedOutputs':bool(retained),'scope':'single copied resize skill, fresh runtime, native PNG/PSD/project geometry; synthetic product fixture, no creative quality acceptance'},file,indent=2)
if __name__=='__main__':unittest.main()
