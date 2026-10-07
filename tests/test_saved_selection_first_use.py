"""命名选区通道及活动选区须真实保存，蒙版返工不能改变非目标内容。"""
from pathlib import Path
import hashlib,importlib.util,json,os,re,shutil,tempfile,unittest,zipfile
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def tree(p):return {str(x.relative_to(p)):digest(x) for x in p.rglob('*') if x.is_file()}
def manifest(p):
 with zipfile.ZipFile(p) as z:return json.loads(z.read('manifest.json'))['document']
def hashes(value):
 found=set()
 if isinstance(value,dict):
  if isinstance(value.get('hash'),str) and re.fullmatch('[0-9a-f]{64}',value['hash']):found.add(value['hash'])
  for v in value.values():found.update(hashes(v))
 elif isinstance(value,list):
  for v in value:found.update(hashes(v))
 return found
@unittest.skipUnless(os.environ.get('CRAFT_SELECTION_FIRST_USE')=='1','requires declared macOS arm64 public runtime')
class SavedSelectionFirstUseTests(unittest.TestCase):
 def test_saved_selection_active_checkpoint_reopen_revision_and_failures(self):
  from PIL import Image
  source=Path(os.environ.get('CRAFT_INSTALLED_SKILL_ROOT',ROOT/'skills/photocraft-cli-selection'))
  if os.environ.get('CRAFT_SELECTION_OUTPUT_ROOT'):
   work=Path(os.environ['CRAFT_SELECTION_OUTPUT_ROOT']);work.mkdir(parents=True,exist_ok=False)
  else:
   tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);work=Path(tmp.name)
  skill=work/'项目 空格/.agents/skills/photocraft-cli-selection';shutil.copytree(source,skill,ignore=shutil.ignore_patterns('__pycache__'));before=tree(skill);source_before=tree(source);self.assertEqual({p.name for p in skill.parent.iterdir()},{skill.name})
  runtime=work/'runtime 空缓存';self.assertFalse(runtime.exists());spec=importlib.util.spec_from_file_location('selection_commands',skill/'scripts/commands.py');commands=importlib.util.module_from_spec(spec);spec.loader.exec_module(commands);env={k:v for k,v in os.environ.items() if not k.startswith('CRAFT_')};env['PATH']='/usr/bin:/bin';receipts={}
  def run(name,project=None,output=None):
   plan=json.loads((skill/f'examples/saved-selection-{name}.json').read_text());inputs={} if project is None else {'project':str(project)};commands.validate(plan,inputs)
   with patch.dict(os.environ,env,clear=True):result=commands.execute(plan,work/(output or name),runtime_home=runtime,inputs=inputs)
   self.assertEqual(result['result'],'PASS',result.get('error'));self.assertTrue(all(s['state']=='succeeded' for s in result['steps']));receipts[output or name]=result
   return {p['as']:s['result'] for p,s in zip(plan['operations'],result['steps']) if 'as' in p}
  def pixels(path,mode):
   with Image.open(path) as im:self.assertEqual(im.size,(128,80));return im.convert(mode).copy()
  created=run('create');self.assertEqual(created['region']['channel'],0);self.assertEqual(created['backup']['channel'],1);self.assertTrue(created['loaded']['selected']);self.assertEqual(created['channels']['target'],{'kind':'composite'});self.assertEqual(len(created['channels']['alpha']),2);self.assertAlmostEqual(created['channels']['alpha'][0]['opacity'],.35,places=6)
  self.assertEqual(created['channels']['alpha'][0]['name'],'Product Local');self.assertEqual(created['channels']['alpha'][1]['name'],'Protected region');self.assertFalse(created['document']['hasSelection'])
  original=work/'create/project.pcraft';sha=digest(original);stored=manifest(original);active_stored=manifest(work/'create/active-selection.pcraft');self.assertIsNone(stored['selection']);self.assertIsNotNone(active_stored['selection']);self.assertEqual(active_stored['selection'],active_stored['channels'][0]['surface'])
  plane=pixels(work/'create/selection-plane.png','L');values=set(plane.tobytes());self.assertIn(0,values);self.assertIn(255,values);self.assertTrue(any(0<v<255 for v in values))
  preview=pixels(work/'create/preview.png','RGB');self.assertEqual(preview.getpixel((24,40)),(152,152,152));self.assertEqual(preview.getpixel((48,40)),(128,128,128));self.assertEqual(preview.getpixel((110,16)),(39,174,96))
  opened=run('reopen',original);self.assertEqual(opened['channels']['alpha'],created['channels']['alpha']);self.assertFalse(opened['document']['hasSelection']);self.assertTrue(opened['loaded']['selected']);self.assertEqual(pixels(work/'reopen/selection-plane.png','L').tobytes(),plane.tobytes());self.assertEqual(pixels(work/'reopen/preview.png','RGB').tobytes(),preview.tobytes())
  active=run('reopen',work/'create/active-selection.pcraft','active-reopened');self.assertTrue(active['document']['hasSelection']);self.assertEqual(pixels(work/'active-reopened/selection-plane.png','L').tobytes(),plane.tobytes())
  revised=run('revise',original);self.assertEqual(revised['region']['channel'],0);new_file=work/'revise/project.pcraft';new=manifest(new_file);self.assertIsNone(new['selection']);self.assertEqual(len(new['channels']),2);self.assertEqual(new['channels'][1],stored['channels'][1]);self.assertNotEqual(new['channels'][0]['surface'],stored['channels'][0]['surface'])
  self.assertEqual({k:v for k,v in new['channels'][0].items() if k!='surface'},{k:v for k,v in stored['channels'][0].items() if k!='surface'})
  self.assertEqual({x['id'] for x in new['layers']},{x['id'] for x in stored['layers']})
  target=created['adjustment']['layer'];unchanged=[]
  for old in stored['layers']:
   changed=next(x for x in new['layers'] if x['id']==old['id'])
   if old['id']==target:
    self.assertIsNotNone(old['mask']);self.assertNotEqual(old['mask'],changed['mask']);self.assertEqual({k:v for k,v in old.items() if k!='mask'},{k:v for k,v in changed.items() if k!='mask'})
   else:self.assertEqual(changed,old);unchanged.append(old)
  protected_hashes=hashes(unchanged+[stored['channels'][1]])
  with zipfile.ZipFile(original) as a,zipfile.ZipFile(new_file) as b:
   for tile in protected_hashes:self.assertEqual(a.read('tiles/'+tile+'.zst'),b.read('tiles/'+tile+'.zst'))
  moved=pixels(work/'revise/selection-plane.png','L');self.assertEqual(moved.tobytes(),bytes(plane.getpixel((x-16,y)) if x>=16 else 0 for y in range(80) for x in range(128)))
  changed=pixels(work/'revise/preview.png','RGB');self.assertEqual(changed.getpixel((24,40)),(128,128,128));self.assertEqual(changed.getpixel((48,40)),(152,152,152));self.assertEqual(changed.crop((80,0,128,80)).tobytes(),preview.crop((80,0,128,80)).tobytes());self.assertEqual(changed.crop((0,0,128,8)).tobytes(),preview.crop((0,0,128,8)).tobytes())
  again=run('reopen',new_file,'revised-reopened');self.assertEqual(again['channels']['alpha'],revised['channels']['alpha']);self.assertEqual(pixels(work/'revised-reopened/selection-plane.png','L').tobytes(),moved.tobytes());self.assertEqual(pixels(work/'revised-reopened/preview.png','RGB').tobytes(),changed.tobytes())
  failures=[]
  for name,command,params in [('empty','select.loadSelection',{'channel':'Product Local'}),('missing','select.loadSelection',{'channel':'Absent channel'}),('invalidOperation','select.saveSelection',{'channel':'Product Local','operation':'multiply'})]:
   steps=[] if name=='empty' else [{'tool':'doc_open','params':{'path':{'$ref':'project.path'}}}]
   if name=='invalidOperation':steps.append({'command':'select.loadSelection','params':{'channel':'Product Local'}})
   steps += [{'command':command,'params':params},{'tool':'doc_save','params':{'path':{'$output':'forbidden.pcraft'}}}]
   with patch.dict(os.environ,env,clear=True):result=commands.execute({'schema':'craft-command-plan/v1','operations':steps},work/name,runtime_home=runtime,inputs={} if name=='empty' else {'project':str(original)})
   self.assertEqual(result['result'],'FAIL',result)
   if name=='invalidOperation':
    self.assertTrue(any(s.get('command')=='select.loadSelection' and s['state']=='succeeded' for s in result['steps']))
    self.assertIn('operation',result['error']);self.assertNotIn('native_context_disabled',result['error'])
   self.assertFalse((work/name/'forbidden.pcraft').exists());self.assertFalse(any(s.get('tool')=='doc_save' for s in result['steps']));self.assertEqual(digest(original),sha);failures.append({'case':name,'result':'FAIL','error':result['error']})
  self.assertEqual(tree(skill),before);self.assertEqual(tree(source),source_before);self.assertEqual(digest(original),sha)
  if os.environ.get('CRAFT_SELECTION_EVIDENCE_FILE'):
   value={'schema':'craft-saved-selection-first-use/v1','result':'PASS','skill':source.name,'runtimeSha256':receipts['create']['runtimeSha256'],'testFileSha256':digest(Path(__file__)),'skillTreeSha256':hashlib.sha256(json.dumps(before,sort_keys=True).encode()).hexdigest(),'planSha256':{name:digest(skill/f'examples/saved-selection-{name}.json') for name in ('create','reopen','revise')},'createPlanSha256':digest(skill/'examples/saved-selection-create.json'),'commands':sorted({s['command'] for s in receipts['create']['steps'] if s.get('command')}),'activeSelectionNativeReopen':True,'namedChannels':2,'translation':[16,0],'featherFractionalCoverage':True,'protectedTileHashes':sorted(protected_hashes),'originalProjectSha256':sha,'revisedProjectSha256':digest(new_file),'failures':failures,'checks':['single skill public cold installation','active selection saved and reopened','named channel plane pixel identity after reopen','partial feather coverage','targeted channel and mask translation','native manifest non-target layer and backup channel identity','protected tile bytes identity','source and skill files preserved'],'unverified':['all selection/channel command contexts','smart-selection/AI quality','spot/PSD fidelity','other modes/depths','GUI/creative quality'],'scope':'bounded RGB8 saved-selection/feather/mask fixture, not full CM-001'};Path(os.environ['CRAFT_SELECTION_EVIDENCE_FILE']).write_text(json.dumps(value,indent=2)+'\n')
if __name__=='__main__':unittest.main()
