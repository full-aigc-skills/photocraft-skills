"""公开导出技能空缓存验证颜色/透明、来源回执、另存继承及拒绝。"""
import copy,hashlib,importlib.util,json,os,shutil,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
@unittest.skipUnless(os.environ.get('CRAFT_FLAT_EXPORT_FIRST_USE')=='1','explicit native flat-export opt-in')
class FlatExportFirstUse(unittest.TestCase):
 def test_actual_flat_color_alpha_provenance_revision_and_refusal(self):
  retained=os.environ.get('CRAFT_FLAT_EXPORT_OUTPUT')
  if retained:
   root=Path(retained).resolve();root.mkdir(parents=True,exist_ok=False);self.run_case(root)
  else:
   with tempfile.TemporaryDirectory(prefix='photocraft-flat-export-') as tmp:self.run_case(Path(tmp))
 def run_case(self,root):
  from PIL import Image
  original=Path(os.environ.get('CRAFT_INSTALLED_FLAT_EXPORT_SKILL',ROOT/'skills/photocraft-cli-export'))
  skill=root/'.agents/skills/photocraft-cli-export';shutil.copytree(original,skill,ignore=shutil.ignore_patterns('__pycache__'))
  spec=importlib.util.spec_from_file_location('native_flat_workflow',skill/'scripts/workflow.py');w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
  def hashes(folder):return {p.relative_to(folder).as_posix():w.sha(p) for p in folder.rglob('*') if p.is_file()}
  before=hashes(skill);image=root/'generated-fixture.png';im=Image.new('RGBA',(4,4),(230,50,40,128));im.putpixel((0,0),(0,0,0,0));im.putpixel((3,3),(230,50,40,255));im.save(image)
  receipt=root/'provider-fixture.json';receipt.write_text('{"id":"fixture-only-no-service-call","usage":{"images":1}}')
  entry={'kind':'generated','provider':'test-fixture-not-live-provider','model':'fixture-v1','requestId':'fixture-only-no-service-call','assetSha256':w.sha(image),'receipt':{'path':str(receipt),'sha256':w.sha(receipt)},'usage':{'quantity':1,'unit':'images'}}
  plan={'document':{'name':'Transparent export','width':16,'height':16,'background':'transparent'},'assets':{'art':{'path':str(image),'sha256':w.sha(image)}},'assetProvenance':{'art':entry},'operations':[{'command':'asset.place','params':{'asset':'art','center':[8,8]},'as':'art'},{'command':'native.command','params':{'command':'edit.assignProfile','params':{'profile':'srgb'}}}],'exports':[{'format':fmt} for fmt in ['png','tif','webp']],'flatExport':{'colorSpace':'Rgb','transparency':'preserve'}}
  runtime=root/'empty-runtime';self.assertFalse(runtime.exists());source=root/'source';manifest=w.execute(plan,source,runtime)
  report=json.loads((source/'flat-export.json').read_text());self.assertTrue(report['source']['transparentPixels']>0);self.assertEqual(len(report['outputs']),3)
  for item in report['outputs']:
   self.assertEqual(item['observation']['alphaSha256'],report['source']['alphaSha256']);self.assertEqual(item['observation']['iccSha256'],report['source']['iccSha256'])
   with Image.open(source/item['proof']) as proof:self.assertEqual(proof.convert('RGBA').size,(16,16))
  provenance=json.loads((source/'asset-provenance.json').read_text());self.assertEqual((source/'generation-art.json').read_bytes(),receipt.read_bytes());self.assertEqual(provenance['localEditing']['cloudGenerationCalls'],0);self.assertEqual(provenance['generationUsage'][0]['quantity'],1);self.assertEqual(provenance['sourceAuthenticity'],'NOT_PROVEN')
  verified=w.load_module('native_verify').verify(source,runtime);self.assertEqual(verified['flatExportVerification']['status'],'PASS');source_before=hashes(source)
  revision={'expectedProjectSha256':manifest['files']['project.pcraft'],'operations':[{'command':'layer.renameLayer','params':{'layer':manifest['bindings']['art']['layer'],'name':'Revised'}}],'exports':plan['exports'],'flatExport':{**plan['flatExport'],'iccSha256':report['source']['iccSha256']}}
  second=root/'revision';w.execute(revision,second,runtime,source);self.assertEqual((second/'generation-art.json').read_bytes(),receipt.read_bytes());self.assertEqual(w.load_module('native_verify').verify(second,runtime)['result'],'PASS')
  jpeg={**revision,'operations':[],'exports':[{'format':'jpg'}]}
  with self.assertRaisesRegex(ValueError,'flat_transparency_changed'):w.execute(jpeg,root/'jpeg-refused',runtime,source)
  failure=json.loads((root/'jpeg-refused/failure.json').read_text());stage=(root/'jpeg-refused'/failure['stage']).resolve();self.assertTrue((stage/'project.pcraft').is_file());self.assertFalse((root/'jpeg-refused/manifest.json').exists());self.assertFalse((stage/'manifest.json').exists());jpeg_loss=json.loads((stage/'flat-export.json').read_text());self.assertEqual(jpeg_loss['status'],'FAIL')
  stage_before=hashes(stage)
  installed=w.load_module('bootstrap').install(json.loads((skill/'scripts/runtime.lock.json').read_text()),runtime)
  with w.load_module('mcp_session').Session([installed['executable'],'mcp','--automation-read-root',str(stage),'--automation-write-root',str(root)]) as session:
   parse=w.load_module('commands').parse_reply;parse(session.request('tools/call',{'name':'doc_open','arguments':{'path':'project.pcraft'}}));actual=parse(session.request('tools/call',{'name':'doc_inspect','arguments':{}}));self.assertEqual(actual['width'],16)
  self.assertEqual(hashes(stage),stage_before)
  opaque=copy.deepcopy(jpeg);opaque['flatExport']={'colorSpace':'Rgb','transparency':'opaque'};w.execute(opaque,root/'jpeg-opaque',runtime,source)
  wrong={**revision,'flatExport':{'iccSha256':'0'*64}}
  with self.assertRaisesRegex(ValueError,'flat_icc_mismatch'):w.execute(wrong,root/'icc-refused',runtime,source)
  bad=copy.deepcopy(plan);bad['assetProvenance']['art']['receipt']['sha256']='0'*64
  with self.assertRaisesRegex(ValueError,'generation_receipt_checksum'):w.execute(bad,root/'receipt-refused',root/'never-runtime')
  self.assertFalse((root/'receipt-refused').exists());self.assertFalse((root/'never-runtime').exists())
  replaced_asset=root/'replacement.png';Image.new('RGBA',(4,4),(20,180,60,255)).save(replaced_asset)
  replacement={**revision,'operations':[],'assets':{'art':{'path':str(replaced_asset),'sha256':w.sha(replaced_asset)}}};replacement.pop('flatExport');w.execute(replacement,root/'replacement',runtime,source);replacement_record=json.loads((root/'replacement/asset-provenance.json').read_text());self.assertEqual(replacement_record['assets']['art']['kind'],'provided');self.assertEqual(replacement_record['generationUsage'],[]);self.assertFalse((root/'replacement/generation-art.json').exists())
  moved=root/'移动 交付';shutil.copytree(source,moved);w.load_module('delivery').validate_delivery(moved,w.sha(source/'manifest.json'));(moved/'design.png').write_bytes(b'replaced')
  with self.assertRaisesRegex(ValueError,'delivery_file_checksum_mismatch'):w.load_module('delivery').validate_delivery(moved)
  forged=root/'forged-profile';shutil.copytree(source,forged);report2=json.loads((forged/'flat-export.json').read_text());report2['outputs'][0]['observation']['profile']={'forged':True};(forged/'flat-export.json').write_text(json.dumps(report2));m=json.loads((forged/'manifest.json').read_text());m['files']['flat-export.json']=w.sha(forged/'flat-export.json');(forged/'manifest.json').write_text(json.dumps(m));w.load_module('delivery').validate_delivery(forged)
  with self.assertRaisesRegex(ValueError,'flat_export_observation_changed'):w.load_module('native_verify').verify(forged,runtime)
  self.assertEqual(hashes(source),source_before);self.assertEqual(hashes(skill),before)
  proof={'schema':'photocraft-flat-export-first-use/v1','status':'PASS','coldSingleSkill':True,'nativeAndFlatFreshReopen':True,'flatReport':report,'provenance':provenance,'transparentJpegRefused':jpeg_loss,'opaqueJpegAccepted':True,'wrongIccRefused':True,'badReceiptZeroRuntimeAndOutput':True,'movedDeliveryAndSameNameReplacement':True,'replacementDoesNotInheritOldReceipt':True,'sourceAndSkillUnchanged':True,'failedNativeStageFreshReopenAndUnchanged':True,'coherentForgedObservationRefusedByFreshReopen':True,'driverSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'scope':'source candidate native RGB8 import/export and fixture provenance; no live generation, verified billing, external print or creative acceptance'}
  if os.environ.get('CRAFT_FLAT_EXPORT_REPORT'):Path(os.environ['CRAFT_FLAT_EXPORT_REPORT']).write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n')
