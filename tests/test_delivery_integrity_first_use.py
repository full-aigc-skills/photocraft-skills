"""单技能真实首用：可移动分层交付的完整性和篡改拒绝。"""
import hashlib,json,os,shutil,subprocess,sys,unittest
from pathlib import Path
from test_native_workflow import product_fixture
ROOT=Path(__file__).resolve().parents[1]
@unittest.skipUnless(os.environ.get('CRAFT_PHOTO_DELIVERY_FIRST_USE')=='1','requires retained output, macOS arm64 and public runtime')
class DeliveryFirstUse(unittest.TestCase):
 def test_moved_editable_poster_revision_and_tamper_refusal(self):
  root=Path(os.environ['CRAFT_PHOTO_DELIVERY_OUTPUT']);root.mkdir(parents=True,exist_ok=False)
  source=Path(os.environ.get('CRAFT_PHOTO_DELIVERY_SKILL',ROOT/'skills/photocraft-cli-export'))
  skill=root/'.agents/skills/photocraft-cli-export';shutil.copytree(source,skill,ignore=shutil.ignore_patterns('__pycache__'))
  runtime=root/'fresh-runtime';environment=dict(os.environ,PATH='/usr/bin:/bin')
  for key in ('CRAFT_RUNTIME_HOME','CRAFT_NODE_ARCHIVE','CRAFT_BUNDLE_DIRECTORY','CRAFT_NATIVE_ARCHIVE_DIRECTORY'):environment.pop(key,None)
  def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
  calls=[]
  def run(script,args,expected=0):
   result=subprocess.run([sys.executable,'-I','-B',str(skill/'scripts'/script),*map(str,args)],env=environment,capture_output=True,text=True,timeout=300)
   log=root/('call-%02d.log'%len(calls));log.write_text(result.stdout+result.stderr);calls.append({'script':script,'exitCode':result.returncode,'logSha256':digest(log)})
   self.assertEqual(result.returncode,expected,result.stdout+result.stderr);return json.loads(result.stdout)
  image=root/'product.png';product_fixture(image);plan=json.loads((skill/'examples/poster-plan.json').read_text());path=root/'plan.json';path.write_text(json.dumps(plan))
  original=root/'poster';run('workflow.py',[path,'--output',original,'--runtime-home',runtime,'--asset','product='+str(image)])
  inspected=json.loads((original/'native.json').read_text());self.assertEqual({x['name'] for x in inspected['layers']},{'Product','Headline','Caption','Background'})
  self.assertTrue(next(x for x in inspected['layers'] if x['name']=='Product')['hasMask'])
  self.assertEqual(next(x for x in inspected['layers'] if x['name']=='Headline')['kind'],'Type')
  manifest_digest=digest(original/'manifest.json');manifest=json.loads((original/'manifest.json').read_text());image.unlink()
  moved=root/'移动 海报';original.rename(moved)
  integrity=run('delivery.py',[moved,'--expected-manifest-sha256',manifest_digest]);self.assertEqual(integrity['result'],'PASS')
  before={str(p.relative_to(moved)):digest(p) for p in moved.rglob('*') if p.is_file()}
  revision={'expectedProjectSha256':manifest['files']['project.pcraft'],'expectedManifestSha256':manifest_digest,'minimumLayers':4,'operations':[{'command':'type.edit','params':{'layer':{'$ref':'headline.layer'},'text':'NOVA PLUS'}}],'exports':plan['exports']}
  revision_path=root/'revision.json';revision_path.write_text(json.dumps(revision));target=root/'revised'
  run('workflow.py',[revision_path,'--source',moved,'--output',target,'--runtime-home',runtime]);self.assertEqual(run('delivery.py',[target])['result'],'PASS')
  changed=json.loads((target/'native.json').read_text());layers={x['name']:x for x in changed['layers']};self.assertEqual(layers['Headline']['text']['text'],'NOVA PLUS')
  for item in inspected['layers']:
   if item['name']!='Headline':self.assertEqual(layers[item['name']],item)
  self.assertEqual(before,{str(p.relative_to(moved)):digest(p) for p in moved.rglob('*') if p.is_file()})
  (moved/'design.png').write_bytes(b'replaced same filename')
  refused=run('delivery.py',[moved],1);self.assertIn('delivery_file_checksum_mismatch',refused['error'])
  never=root/'never-installed';failed=run('workflow.py',[revision_path,'--source',moved,'--output',root/'blocked','--runtime-home',never],1)
  self.assertIn('delivery_file_checksum_mismatch',failed['error']);self.assertFalse(never.exists());self.assertFalse((root/'blocked').exists())
  self.assertFalse(any(skill.rglob('*.pyc')))
  proof={'schema':'photocraft-delivery-first-use/v1','result':'PASS','coldSingleSkill':True,'manifestSha256':manifest_digest,'originalFiles':before,'revisedManifestSha256':digest(target/'manifest.json'),'layers':[{'name':x['name'],'id':x['id'],'kind':x['kind']} for x in inspected['layers']],'publicIntegrity':integrity,'tamperRefusedBeforeInstall':True,'movedAfterOriginalAssetDeleted':True,'calls':calls,'scope':'Native masked poster and text revision, public integrity; not all PSD fidelity, all commands, human creative approval or full V1.'}
  (root/'proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':unittest.main()
