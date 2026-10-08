"""平面导出约束和素材来源必须绑定实际文件，不能只信声明。"""
import importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
def module(name):
 spec=importlib.util.spec_from_file_location('flat_test_'+name,ROOT/'skills/photocraft-use/scripts'/(name+'.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
class FlatExportTests(unittest.TestCase):
 def test_invalid_export_policy_refuses_before_runtime_and_output(self):
  w=module('workflow')
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)
   for policy in [{'transparency':'surprise'},{'iccSha256':'x'},{'colorSpace':'sRGB'},{'unknown':True}]:
    with self.subTest(policy=policy),patch.object(w,'load_module',wraps=w.load_module) as loader,self.assertRaisesRegex(ValueError,'invalid_flat_export'):
     w.execute({'document':{'width':8,'height':8},'operations':[],'exports':[{'format':'png'}],'flatExport':policy},root/'out',root/'runtime')
    self.assertFalse((root/'out').exists());self.assertFalse((root/'runtime').exists());self.assertNotIn('bootstrap',[c.args[0] for c in loader.call_args_list])
 def test_alpha_requirement_uses_full_actual_surface_and_rejects_opaque_loss(self):
  m=module('flat_export');a={'width':2,'height':1,'alphaSha256':'a'*64,'transparentPixels':1,'mode':'Rgb','iccSha256':None};b={**a,'alphaSha256':'b'*64,'transparentPixels':0}
  with self.assertRaisesRegex(ValueError,'flat_transparency_changed'):m.check({'transparency':'preserve'},a,b)
  with self.assertRaisesRegex(ValueError,'flat_transparency_not_opaque'):m.check({'transparency':'opaque'},a,a)
  m.check({'transparency':'preserve'},a,a)
 def test_color_and_icc_claims_are_checked_not_copied(self):
  m=module('flat_export');a={'mode':'Rgb','iccSha256':'a'*64,'transparentPixels':0,'width':1,'height':1,'alphaSha256':'b'*64}
  with self.assertRaisesRegex(ValueError,'flat_color_space_mismatch'):m.check({'colorSpace':'Cmyk'},a,a)
  with self.assertRaisesRegex(ValueError,'flat_icc_mismatch'):m.check({'iccSha256':'c'*64},a,a)
 def test_generation_receipt_requires_registered_asset_and_exact_bytes(self):
  m=module('flat_export')
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);receipt=root/'receipt.json';receipt.write_text('{"id":"original-provider-reply"}')
   entry={'kind':'generated','provider':'fixture-provider','model':'fixture-model','requestId':'r1','assetSha256':'a'*64,'receipt':{'path':str(receipt),'sha256':'b'*64},'usage':{'quantity':1,'unit':'images'}}
   with self.assertRaisesRegex(ValueError,'generation_receipt_checksum'):m.provenance_preflight({'assetProvenance':{'product':entry},'assets':{'product':{'path':'unused','sha256':'a'*64}}},{},None)
   entry['receipt']['sha256']=m.sha(receipt);m.provenance_preflight({'assetProvenance':{'product':entry},'assets':{'product':{'path':'unused','sha256':'a'*64}}},{},None)
   entry['assetSha256']='c'*64
   with self.assertRaisesRegex(ValueError,'generation_asset_identity'):m.provenance_preflight({'assetProvenance':{'product':entry},'assets':{'product':{'path':'unused','sha256':'a'*64}}},{},None)
 def test_unknown_source_cannot_be_invented_as_generated_or_billed(self):
  m=module('flat_export')
  for value in [{'kind':'generated'},{'kind':'provided','usage':{'quantity':1,'unit':'credits'}}]:
   with self.subTest(value=value),self.assertRaisesRegex(ValueError,'invalid_asset_provenance'):m.validate_provenance({'assetProvenance':{'asset':value}})
 def test_required_reports_cannot_be_removed_from_delivery(self):
  m=module('flat_export')
  with tempfile.TemporaryDirectory() as tmp:
   for plan,error in [({'flatExport':{}},'flat_report_missing'),({'assetProvenance':{}},'generation_report_missing')]:
    with self.subTest(plan=plan),self.assertRaisesRegex(ValueError,error):m.validate_saved(Path(tmp),plan,{'files':{},'assets':{}})
 def test_malformed_bound_report_returns_a_validation_error(self):
  m=module('flat_export')
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);report={'schema':'photocraft-flat-export/v1','status':'PASS','policy':{},'nativeSha256':'a'*64,'sourceProjectSha256':None,'outputs':[{'path':'design.png'}]};(root/'flat-export.json').write_text(json.dumps(report))
   with self.assertRaisesRegex(ValueError,'flat_report_invalid'):m.validate_saved(root,{'flatExport':{},'exports':[{'format':'png'}]},{'files':{'project.pcraft':'a'*64,'flat-export.json':'b'*64,'flat-source.png':'c'*64},'assets':{}})
if __name__=='__main__':unittest.main()
