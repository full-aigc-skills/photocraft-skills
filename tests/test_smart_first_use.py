"""单技能公开智能对象放置、替换和移动工程的真实首次使用。"""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

def hashes(root):return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}

@unittest.skipUnless(os.environ.get('CRAFT_SMART_FIRST_USE')=='1','requires Pillow and public native runtime downloads')
class SmartFirstUse(unittest.TestCase):
 def test_smart_replace_relink_move_and_preservation(self):
  from PIL import Image
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);source=Path(os.environ.get('CRAFT_INSTALLED_SMART_SKILL',Path(__file__).resolve().parents[1]/'skills/photocraft-cli-layers'));skill=root/'.agents/skills/photocraft-cli-layers';shutil.copytree(source,skill,ignore=shutil.ignore_patterns('__pycache__'));baseline=hashes(skill);runtime=root/'empty-runtime'
   self.assertFalse(runtime.exists())
   if os.environ.get('CRAFT_SMART_CANDIDATE_ARCHIVE'):
    result=subprocess.run([sys.executable,'-I','-B',str(skill/'scripts/bootstrap.py'),'--runtime-home',str(runtime),'--archive',os.environ['CRAFT_SMART_CANDIDATE_ARCHIVE']],capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stdout+result.stderr)
   red=root/'red.png';green=root/'green.png';blue=root/'blue.png'
   for p,color in [(red,'red'),(green,'green'),(blue,'blue')]:Image.new('RGBA',(16,16),color).save(p)
   def run(plan,out,source=None,assets=(),expected=0):
    path=root/'plan.json';path.write_text(json.dumps(plan));argv=[sys.executable,'-I','-B',str(skill/'scripts/workflow.py'),str(path),'--output',str(out),'--runtime-home',str(runtime)]
    if source:argv+=['--source',str(source)]
    for assignment in assets:argv+=['--asset',assignment]
    result=subprocess.run(argv,capture_output=True,text=True,env=dict(os.environ,PATH='/usr/bin:/bin'),timeout=600);self.assertEqual(result.returncode,expected,result.stdout+result.stderr);return json.loads(result.stdout)
   initial={'document':{'name':'Product smart poster','width':64,'height':64,'background':'#ffffff'},'operations':[{'command':'shape.create','params':{'shape':'rectangle','rect':[0,0,8,8],'fill':'#0000ff'},'as':'badge'},{'command':'asset.placeSmart','params':{'asset':'product','center':[32,32],'fit':False,'scale':100},'as':'product'},{'command':'layer.layerMask.revealAll','params':{'layer':{'$ref':'product.layer'}}}],'exports':[{'format':'png'}],'minimumLayers':2}
   first=root/'first';manifest=run(initial,first,assets=['product='+str(red)]);native=json.loads((first/'native.json').read_text());old=hashes(first)
   if os.environ.get('CRAFT_SMART_DEBUG'):Path(os.environ['CRAFT_SMART_DEBUG']).write_text(json.dumps(native,indent=2))
   product=manifest['bindings']['product']['layer'];layer=lambda doc:next(l for l in doc['layers'] if l['id']==product)
   self.assertIn('smart',layer(native)['kind'].lower())
   def revised(command,src,out,asset):
    prior=json.loads((src/'manifest.json').read_text());return run({'expectedProjectSha256':prior['files']['project.pcraft'],'operations':[{'command':command,'params':{'layer':product,'asset':'replacement'}}],'exports':[{'format':'png'}]},out,src,['replacement='+str(asset)])
   second=root/'second';revised('layer.smartObjects.replaceContents',first,second,green);after=json.loads((second/'native.json').read_text())
   self.assertEqual([l for l in native['layers'] if l['id']!=product],[l for l in after['layers'] if l['id']!=product])
   self.assertTrue(layer(native)['hasMask']);self.assertTrue(layer(after)['hasMask'])
   self.assertEqual(layer(native)['smartTransform'],layer(after)['smartTransform'])
   self.assertEqual(layer(after)['smartSourceKind'],'embedded')
   self.assertEqual(old,hashes(first));moved=root/'moved';shutil.copytree(second,moved);saved=hashes(moved);shutil.rmtree(second);red.unlink();green.unlink()
   third=root/'third';revised('layer.smartObjects.relinkToFile',moved,third,blue);final=json.loads((third/'native.json').read_text());self.assertIn('smart',layer(final)['kind'].lower());self.assertEqual(saved,hashes(moved));self.assertEqual(old,hashes(first))
   with Image.open(first/'design.png') as img:self.assertEqual(img.convert('RGB').getpixel((32,32)),(255,0,0))
   with Image.open(moved/'design.png') as img:self.assertEqual(img.convert('RGB').getpixel((32,32)),(0,128,0))
   with Image.open(third/'design.png') as img:self.assertEqual(img.convert('RGB').getpixel((32,32)),(0,0,255))
   invalid={'expectedProjectSha256':json.loads((third/'manifest.json').read_text())['files']['project.pcraft'],'operations':[{'command':'layer.smartObjects.replaceContents','params':{'layer':product,'path':'/outside'}}]};bad=root/'bad';run(invalid,bad,third,expected=1);self.assertFalse(bad.exists());self.assertEqual(baseline,hashes(skill))
   if os.environ.get('CRAFT_SMART_EVIDENCE'):
    proof={'schema':'photocraft-smart-candidate-first-use/v1','result':'PASS','scope':('single copied source skill; locally checksummed candidate archive installed before workflow' if os.environ.get('CRAFT_SMART_CANDIDATE_ARCHIVE') else 'single copied skill; empty runtime public downloads')+'; editable embedded smart replacement and relink collection','runtimeSha256':manifest['runtimeSha256'],'smartLayerId':product,'pixelChecks':3,'sourcePreserved':True,'movedPackagePreserved':True,'skillPreserved':True,'invalidPathRejected':True,'driverSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'excluded':['persistent external linked delivery','all smart filters','external PSD editor','creative acceptance']+([] if os.environ.get('CRAFT_INSTALLED_SMART_SKILL') else ['fixed plugin installation'])}
    with Path(os.environ['CRAFT_SMART_EVIDENCE']).open('x') as stream:json.dump(proof,stream,indent=2)
if __name__=='__main__':unittest.main()
