"""交付包变更必须在安装与编辑之前拒绝；校验不代替创作验收。"""
import hashlib,importlib.util,json
from pathlib import Path
import tempfile,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
def module(name):
 spec=importlib.util.spec_from_file_location('photo_integrity_'+name,ROOT/'skills/photocraft-use/scripts'/(name+'.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
class DeliveryIntegrityTests(unittest.TestCase):
 def fixture(self,root):
  root.mkdir();files={'project.pcraft':b'native','native.json':b'{}','design.png':b'preview','operations.json':b'[]','plan.json':b'{}'}
  for name,data in files.items():(root/name).write_bytes(data)
  hashes={n:hashlib.sha256(data).hexdigest() for n,data in files.items()}
  loss={'schema':'craft-exchange-loss/v1','pluginId':'photocraft','native':{'location':'project.pcraft','sha256':hashes['project.pcraft']},'inspection':{'location':'native.json','sha256':hashes['native.json']},'outputs':[{'location':'design.png','sha256':hashes['design.png'],'nativeSubstitute':False,'role':'derivative'}]}
  (root/'exchange-loss.json').write_text(json.dumps(loss));hashes['exchange-loss.json']=hashlib.sha256((root/'exchange-loss.json').read_bytes()).hexdigest()
  manifest={'schema':'photocraft-delivery/v1','files':hashes,'bindings':{},'assets':{},'outputs':[{'path':'design.png'}],'lossReport':{'path':'exchange-loss.json','sha256':hashes['exchange-loss.json']}}
  (root/'manifest.json').write_text(json.dumps(manifest));return manifest
 def test_changed_preview_is_rejected_before_runtime_install(self):
  workflow=module('workflow')
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);source=root/'source';m=self.fixture(source);(source/'design.png').write_bytes(b'replaced')
   plan={'expectedProjectSha256':m['files']['project.pcraft'],'operations':[]}
   original=workflow.load_module
   def load(name):
    if name=='bootstrap':raise AssertionError('runtime reached before complete source integrity check')
    return original(name)
   with patch.object(workflow,'load_module',side_effect=load),self.assertRaisesRegex(ValueError,'delivery_file_checksum_mismatch'):
    workflow.execute(plan,root/'output',runtime_home=root/'runtime',source=source)
   self.assertFalse((root/'output').exists());self.assertFalse((root/'runtime').exists())
 def test_valid_moved_package_and_external_manifest_binding(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);source=root/'source';m=self.fixture(source);digest=hashlib.sha256((source/'manifest.json').read_bytes()).hexdigest();source.rename(root/'移动 交付')
   v=module('delivery');self.assertEqual(v.validate_delivery(root/'移动 交付',digest),m)
   with self.assertRaisesRegex(ValueError,'delivery_manifest_checksum_mismatch'):v.validate_delivery(root/'移动 交付','0'*64)
 def test_bad_paths_symlink_and_duplicate_keys_are_rejected(self):
  v=module('delivery')
  for name in ('../outside','/outside','nested/../outside','a\\b','./design.png','C:outside'):
   with self.subTest(name=name),tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp)/'package';m=self.fixture(root);m['files'][name]='0'*64;(root/'manifest.json').write_text(json.dumps(m))
    with self.assertRaisesRegex(ValueError,'delivery_path_invalid'):v.validate_delivery(root)
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)/'package';self.fixture(root);(root/'design.png').unlink();(root/'design.png').symlink_to(root/'project.pcraft')
   with self.assertRaisesRegex(ValueError,'delivery_file_missing_or_escaping'):v.validate_delivery(root)
   (root/'manifest.json').write_text('{"schema":"a","schema":"b"}')
   with self.assertRaisesRegex(ValueError,'duplicate_json_key'):v.validate_delivery(root)
 def test_layout_reference_must_match_manifest_file(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)/'package';m=self.fixture(root);m['layoutVariant']={'path':'native.json','sha256':'0'*64};(root/'manifest.json').write_text(json.dumps(m))
   with self.assertRaisesRegex(ValueError,'delivery_reference_identity_mismatch'):module('delivery').validate_delivery(root)
 def test_loss_report_identity_must_match_even_when_its_file_hash_is_updated(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)/'package';m=self.fixture(root);loss=json.loads((root/'exchange-loss.json').read_text());loss['native']['sha256']='0'*64;(root/'exchange-loss.json').write_text(json.dumps(loss));digest=hashlib.sha256((root/'exchange-loss.json').read_bytes()).hexdigest();m['files']['exchange-loss.json']=digest;m['lossReport']['sha256']=digest;(root/'manifest.json').write_text(json.dumps(m))
   with self.assertRaisesRegex(ValueError,'delivery_loss_identity_mismatch'):module('delivery').validate_delivery(root)
if __name__=='__main__':unittest.main()
