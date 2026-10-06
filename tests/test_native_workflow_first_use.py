"""单技能公开工作流完整命令网关：冷安装、实际原生保存与重开、返工及原交付保全。"""
import hashlib,json,os,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];DOMAIN=ROOT.name.removesuffix('-skills')
@unittest.skipUnless(os.environ.get('CRAFT_NATIVE_WORKFLOW_FIRST_USE')=='1','explicit native opt-in')
class NativeFirstUse(unittest.TestCase):
 def test_public_delivery_and_revision(self):
  from PIL import Image
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary);skill=root/'single-skill';shutil.copytree(ROOT/'skills'/(DOMAIN+'-use'),skill);runtime=root/'empty-runtime'
   plan=json.loads((skill/'examples/native-workflow.json').read_text())
   if DOMAIN=='filmcraft':
    image=root/'still.png';Image.new('RGBA',(32,32),(239,91,54,255)).save(image);plan['assets']={'still':{'path':str(image),'sha256':hashlib.sha256(image.read_bytes()).hexdigest()}}
   def run(p,output,source=None):
    f=root/(output.name+'.json');f.write_text(json.dumps(p));argv=[sys.executable,'-I','-B',str(skill/'scripts/workflow.py'),str(f),'--output',str(output),'--runtime-home',str(runtime)]
    if source:argv+=['--source',str(source)]
    result=subprocess.run(argv,capture_output=True,text=True,timeout=300,env=dict(os.environ,PATH='/usr/bin:/bin'));self.assertEqual(result.returncode,0,result.stdout+result.stderr)
    manifest=json.loads((output/'manifest.json').read_text());self.assertEqual(manifest['schema'],DOMAIN+'-delivery/v1')
    self.assertTrue((output/'native.json').is_file());self.assertTrue((output/'exchange-loss.json').is_file());self.assertIn('nativeCommand',(output/'operations.json').read_text())
    for name,sha in manifest['files'].items():self.assertEqual(hashlib.sha256((output/name).read_bytes()).hexdigest(),sha)
    pngs=list(output.glob('*.png'));self.assertTrue(pngs)
    for png in pngs:
     with Image.open(png) as img:img.load();self.assertEqual(img.size,(32,32))
    return manifest
   original=root/'original';manifest=run(plan,original);suffix={'filmcraft':'fcproj','effectcraft':'ecproj','photocraft':'pcraft','vectorcraft':'vectorcraft'}[DOMAIN];project='project.'+suffix
   before={str(p.relative_to(original)):hashlib.sha256(p.read_bytes()).hexdigest() for p in original.rglob('*') if p.is_file()}
   revision={k:v for k,v in plan.items() if k not in ['document','assets']};revision['expectedProjectSha256']=manifest['files'][project];revision['operations']=[plan['operations'][-1]]
   if DOMAIN=='filmcraft':revision['operations'].insert(0,{'command':'timeline.select','params':{'clips':{'$ref':'clip.clips'},'add':False,'toggle':False}})
   if DOMAIN=='effectcraft':revision['operations'].insert(0,{'command':'layer.select','params':{'layers':[{'$ref':'badge.layer'}],'add':False,'toggle':False}})
   params=revision['operations'][-1]['params']['params'];params.update({'filmcraft':{'speed':200},'effectcraft':{'mode':'Normal'},'photocraft':{'opacity':.5},'vectorcraft':{'color':'#0000ff'}}[DOMAIN])
   revised=run(revision,root/'revised',original);self.assertNotEqual(manifest['files'][project],revised['files'][project])
   self.assertEqual(before,{str(p.relative_to(original)):hashlib.sha256(p.read_bytes()).hexdigest() for p in original.rglob('*') if p.is_file()})
   if os.environ.get('CRAFT_NATIVE_WORKFLOW_REPORT'):Path(os.environ['CRAFT_NATIVE_WORKFLOW_REPORT']).write_text(json.dumps({'domain':DOMAIN,'result':'PASS','entrySha256':hashlib.sha256((skill/'scripts/native_workflow.py').read_bytes()).hexdigest(),'projectSha256':manifest['files'][project],'revisionSha256':revised['files'][project],'scope':'candidate single-skill cold native workflow delivery and revision; not fixed release or full DAG acceptance'},indent=2)+'\n')
