"""局部调整示例必须随每个可独立安装的技能交付。"""
import json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class AdjustmentMaskContract(unittest.TestCase):
 def test_every_independent_skill_has_paired_recipes_and_usage(self):
  for skill in (ROOT/'skills').iterdir():
   if not (skill/'SKILL.md').exists():continue
   catalog={r['id']:r for r in json.loads((skill/'references/command-coverage.json').read_text())['commands']}
   for name in ['adjustment-mask-create.json','adjustment-mask-revise.json']:
    for op in json.loads((skill/'examples'/name).read_text())['operations']:
     command=op['params']['command'] if op['command']=='native.command' else op['command'];self.assertIn(command,catalog);self.assertIn('examples/'+name,catalog[command].get('usageRecipes',[]))
   self.assertIn('references/adjustment-mask.md',(skill/'SKILL.md').read_text());self.assertTrue((skill/'references/adjustment-mask.md').exists())

import hashlib,os,shutil,subprocess,sys,tempfile

def hashes(root):return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}

@unittest.skipUnless(os.environ.get('CRAFT_PHOTO_ADJUSTMENT_FIRST_USE')=='1','explicit native public first-use opt-in')
class AdjustmentMaskNative(unittest.TestCase):
 def test_saved_mask_local_pixels_revision_and_wrong_kind_rejection(self):
  from PIL import Image
  original=Path(os.environ.get('CRAFT_PHOTO_ADJUSTMENT_SKILL',ROOT/'skills/photocraft-cli-adjustments'));before=hashes(original)
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);skill=root/'.agents/skills'/original.name;shutil.copytree(original,skill,ignore=shutil.ignore_patterns('__pycache__'));copied=hashes(skill);runtime=root/'empty-runtime';self.assertFalse(runtime.exists())
   def run(plan,out,source=None,ok=True):
    p=root/(out.name+'.json');p.write_text(json.dumps(plan));args=[sys.executable,'-I','-B',str(skill/'scripts/workflow.py'),str(p),'--output',str(out),'--runtime-home',str(runtime)]
    if source:args+=['--source',str(source)]
    r=subprocess.run(args,capture_output=True,text=True,env=dict(os.environ,PATH='/usr/bin:/bin'),timeout=600)
    if not ok:self.assertNotEqual(r.returncode,0);self.assertFalse((out/'manifest.json').exists());return r.stdout+r.stderr
    self.assertEqual(r.returncode,0,r.stdout+r.stderr);m=json.loads((out/'manifest.json').read_text());self.assertTrue((out/'project.pcraft').is_file());self.assertTrue((out/'exchange-loss.json').is_file())
    for f,sha in m['files'].items():self.assertEqual(hashlib.sha256((out/f).read_bytes()).hexdigest(),sha)
    return m,json.loads((out/'native.json').read_text())
   plan=json.loads((skill/'examples/adjustment-mask-create.json').read_text());first=root/'original';m,n=run(plan,first);old=hashes(first)
   def pixels(folder):
    with Image.open(folder/'design.png') as im:
     im=im.convert('RGBA');self.assertEqual(im.size,(128,64));return im.getpixel((16,32)),im.crop((32,0,128,64)).tobytes()
   a,control=pixels(first);self.assertGreater(a[0],128);layers={x['id']:x for x in n['layers']};adjustment=m['bindings']['adjustment']['layer'];self.assertEqual(layers[adjustment]['kind'],'Adjustment');self.assertTrue(layers[adjustment]['hasMask'])
   revision=json.loads((skill/'examples/adjustment-mask-revise.json').read_text());revision['expectedProjectSha256']=m['files']['project.pcraft'];second=root/'revised';new,nn=run(revision,second,first);b,newcontrol=pixels(second);self.assertLess(b[0],128);self.assertEqual(control,newcontrol);newlayers={x['id']:x for x in nn['layers']};self.assertEqual(set(layers),set(newlayers));self.assertTrue(newlayers[adjustment]['hasMask']);self.assertEqual(layers[adjustment]['adjustment']['BrightnessContrast']['brightness'],30);self.assertEqual(newlayers[adjustment]['adjustment']['BrightnessContrast']['brightness'],-30)
   for id,l in layers.items():
    if id!=adjustment:self.assertEqual({k:v for k,v in l.items() if k!='selected'},{k:v for k,v in newlayers[id].items() if k!='selected'})
   self.assertEqual(old,hashes(first));self.assertNotEqual(m['files']['project.pcraft'],new['files']['project.pcraft'])
   bad=json.loads(json.dumps(revision));bad['operations'][0]['params']['params']['layer']={'$ref':'target.layer'};bad['operations'][1]['params']['params']['layer']={'$ref':'target.layer'};error=run(bad,root/'rejected',first,False);self.assertTrue(any(s in error.lower() for s in ['adjustment','precondition_failed']));self.assertEqual(old,hashes(first));self.assertEqual(before,hashes(original));self.assertEqual(copied,hashes(skill));self.assertFalse(list(skill.rglob('*.pyc')))
   if os.environ.get('CRAFT_PHOTO_ADJUSTMENT_REPORT'):
    Path(os.environ['CRAFT_PHOTO_ADJUSTMENT_REPORT']).write_text(json.dumps({'schema':'photocraft-adjustment-mask-first-use/v1','result':'PASS','skill':original.name,'nativeProjectSha256':m['files']['project.pcraft'],'revisionSha256':new['files']['project.pcraft'],'initialPixel':a,'revisedPixel':b,'maskPersisted':True,'controlPixelsUnchanged':True,'nonTargetLayersPreserved':True,'originalDeliveryPreserved':True,'wrongLayerKindRejected':True,'skillIdentityUnchanged':True,'scope':'native mask/brightness sample; not exhaustive748 commands, PSD fidelity, GUI or fullV1'},indent=2)+'\n')
