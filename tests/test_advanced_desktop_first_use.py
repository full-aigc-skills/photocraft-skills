"""固定安装技能在真实桌面执行进阶命令、原生重开和渲染；显式原生验收。"""
import hashlib,json,os,shutil,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DOMAIN=ROOT.name.removesuffix('-skills')
@unittest.skipUnless(os.environ.get('CRAFT_ADVANCED_DESKTOP')=='1','native advanced desktop is opt-in')
class AdvancedDesktopFirstUse(unittest.TestCase):
 def test_owned_gui_advanced_plan_persists_objects_and_renders(self):
  from PIL import Image
  source=Path(os.environ['CRAFT_ADVANCED_DESKTOP_SKILL'])
  def hashes(root):return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
  original=hashes(source)
  with tempfile.TemporaryDirectory(prefix='craft-advanced-desktop-') as td:
   root=Path(td);skill=root/'.agents/skills'/source.name;skill.parent.mkdir(parents=True);shutil.copytree(source,skill);before=hashes(skill);plan=json.loads((skill/'examples/commands-advanced.json').read_text());extension={'filmcraft':'fcproj','effectcraft':'ecproj','photocraft':'pcraft','vectorcraft':'vectorcraft'}[DOMAIN];path={'$output':'project.'+extension}
   if DOMAIN=='filmcraft':
    operations=[]
    for op in plan['operations']:
     if op.get('command')=='clip.speedDuration':operations.append({'command':'timeline.select','params':{'clips':op['params']['clips'],'add':False,'toggle':False}})
     operations.append(op)
    plan['operations']=operations+[{'command':'file.open','params':{'path':path}},{'tool':'render_frame','params':{'seconds':0,'max_side':96}},{'command':'sequence.inspect','params':{}}]
   elif DOMAIN=='effectcraft':plan['operations'] += [{'tool':'open_project','params':{'path':path}},{'tool':'render_frame','params':{'path':{'$output':'preview.png'},'time':0.5,'max_side':96,'transparent':True}},{'tool':'get_project','params':{}}]
   elif DOMAIN=='photocraft':plan['operations'] += [{'tool':'doc_open','params':{'path':path}},{'tool':'doc_inspect','params':{}}]
   else:plan['operations'] += [{'command':'document.open','params':{'path':path}},{'tool':'inspect_document','params':{}}]
   plan['operations'].insert(-1,{'tool':'inspect_ui' if DOMAIN=='vectorcraft' else 'ui_inspect','params':{}})
   frozen=root/'plan.json';frozen.write_text(json.dumps(plan));output=root/'output';result=subprocess.run(['/opt/anaconda3/bin/python3','-I','-B',str(skill/'scripts/desktop.py'),'run',str(frozen),'--output',str(output),'--runtime-home',str(root/'runtime')],capture_output=True,text=True,timeout=800,env=dict(os.environ,PATH='/usr/bin:/bin'));self.assertEqual(result.returncode,0,result.stdout+result.stderr)
   receipt=json.loads((output/'success.json').read_text());desktop=json.loads((output/'desktop-session.json').read_text());self.assertEqual(receipt['result'],'PASS');self.assertTrue(desktop['ownedProcessesStopped']);self.assertTrue(desktop['listenerOwnedByPID']);inspection=receipt['steps'][-1]['result']
   if DOMAIN=='filmcraft':self.assertEqual(len(inspection['video'][0]['items']),2)
   elif DOMAIN=='effectcraft':self.assertGreaterEqual(inspection['items'][0]['layers'],3)
   elif DOMAIN=='photocraft':self.assertGreaterEqual(len(inspection['layers']),4)
   else:self.assertGreaterEqual(len(inspection['layers'][0]['children']),2)
   images=list((output/'tool-images').glob('*.png')) if DOMAIN=='filmcraft' else [output/'preview.png'];self.assertTrue(images);renders=[]
   for p in images:
    with Image.open(p) as image:image.load();self.assertGreater(image.width,0);self.assertGreater(image.height,0);renders.append({'name':p.name,'size':image.size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
   project=output/('project.'+extension);self.assertGreater(project.stat().st_size,0);self.assertEqual(hashes(source),original);self.assertEqual(hashes(skill),before)
   proof={'schema':'craft-owned-advanced-desktop-first-use/v1','result':'PASS','domain':DOMAIN,'skill':source.name,'operations':len(receipt['steps']),'plan':plan,'nativeProjectSha256':hashlib.sha256(project.read_bytes()).hexdigest(),'renders':renders,'finalInspection':inspection,'desktopBinarySha256':desktop['desktop']['binarySha256'],'cliBinarySha256':receipt['runtimeSha256'],'ownedProcessesStopped':True,'ownedListenerVerified':True,'desktopControlAddress':desktop['control'],'uiInspection':receipt['steps'][-2]['result'],'skillUnchanged':True,'scope':'pinned skill copied alone, empty desktop+CLI cache, advanced GUI command plan/native reopen/render; not exhaustive commands'}
   Path(os.environ['CRAFT_ADVANCED_DESKTOP_REPORT']).write_text(json.dumps(proof,indent=2)+'\n')
