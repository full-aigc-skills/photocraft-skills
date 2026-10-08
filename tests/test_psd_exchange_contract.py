"""领域PSD门禁保持严格公共交换结构；不以移除门禁换取消费通过。"""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
def load(name):
 spec=importlib.util.spec_from_file_location('exchange_contract_'+name,ROOT/'skills/photocraft-use/scripts'/(name+'.py'))
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def fixture(root):
 native={'layers':[{'name':'Title','kind':'Type','text':{'text':'标题'}}]}
 for name,value in [('native.json',native),('psd-inspection.json',native),('operations.json',[]),('plan.json',{'operations':[],'exports':[{'format':'psd'}],'psdPolicy':{'requiredFeatures':['text']}})]:
  (root/name).write_text(json.dumps(value))
 (root/'project.pcraft').write_bytes(b'native fixture, not a native acceptance')
 (root/'design.psd').write_bytes(b'PSD fixture, not a native acceptance')
 return load('exchange_loss').write_report(root,['design.psd'],{})

def manifest(root,report):
 (root/'exchange-loss.json').write_text(json.dumps(report))
 files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir() if p.name!='manifest.json'}
 value={'schema':'photocraft-delivery/v1','files':files,'assets':{},'outputs':[{'path':'design.psd'}],'lossReport':{'path':'exchange-loss.json','sha256':files['exchange-loss.json']}}
 (root/'manifest.json').write_text(json.dumps(value));return files

class PsdExchangeContract(unittest.TestCase):
 def test_public_exchange_root_stays_fixed_and_gate_is_bound_in_psd_observations(self):
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary);report=fixture(root)
   self.assertEqual(set(report),{'schema','pluginId','native','inspection','psdInspection','outputs','acceptance'})
   ref=report['outputs'][0]['observations']['psdGate']
   self.assertEqual(ref,{'location':'psd-acceptance.json','sha256':hashlib.sha256((root/'psd-acceptance.json').read_bytes()).hexdigest()})
   manifest(root,report);self.assertEqual(load('delivery').validate_delivery(root)['schema'],'photocraft-delivery/v1')

 def test_legacy_top_level_gate_is_readonly_compatible_without_rewriting(self):
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary);report=fixture(root)
   report['psdGate']=report['outputs'][0]['observations'].pop('psdGate')
   manifest(root,report);before={p.name:p.read_bytes() for p in root.iterdir()}
   load('delivery').validate_delivery(root)
   self.assertEqual(before,{p.name:p.read_bytes() for p in root.iterdir()})

 def test_conflicting_gate_references_are_refused_with_consistent_outer_file_hashes(self):
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary);report=fixture(root);report['psdGate']={'location':'psd-acceptance.json','sha256':'f'*64}
   manifest(root,report)
   with self.assertRaisesRegex(ValueError,'delivery_psd_gate_identity_mismatch'):load('delivery').validate_delivery(root)

 def test_wrong_nested_gate_or_removed_gate_never_bypasses_required_policy(self):
  for mode in ['wrong','missing']:
   with self.subTest(mode=mode),tempfile.TemporaryDirectory() as temporary:
    root=Path(temporary);report=fixture(root);observations=report['outputs'][0]['observations']
    if mode=='wrong':observations['psdGate']['sha256']='f'*64
    else:observations.pop('psdGate');(root/'psd-acceptance.json').unlink()
    manifest(root,report)
    with self.assertRaisesRegex(ValueError,'delivery_psd_gate_identity_mismatch' if mode=='wrong' else 'delivery_psd_gate_missing'):load('delivery').validate_delivery(root)

if __name__=='__main__':unittest.main()
