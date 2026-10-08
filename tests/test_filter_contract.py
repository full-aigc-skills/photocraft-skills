import importlib.util
from pathlib import Path
import unittest
SCRIPTS=Path(__file__).resolve().parents[1]/'skills/photocraft-use/scripts'
def module():
 spec=importlib.util.spec_from_file_location('filter_contract',SCRIPTS/'filter_contract.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
class FilterContractTests(unittest.TestCase):
 def setUp(self):self.config={'target':2,'method':'raster','selection':False,'mask':False,'region':[0,0,8,8]};self.model={'activeLayer':2,'hasSelection':False,'layers':[{'id':2,'kind':'Pixel','hasMask':False}]}
 def test_wrong_target_selection_or_mask_cannot_be_treated_as_background_filter(self):
  m=module();m.check(self.config,self.model)
  for model in [{**self.model,'activeLayer':3},{**self.model,'hasSelection':True},{**self.model,'layers':[{'id':2,'kind':'Pixel','hasMask':True}]}]:
   with self.assertRaisesRegex(ValueError,'filter_context_mismatch'):m.check(self.config,model)
 def test_raster_is_declared_baked_and_unobserved_smart_editability_is_refused(self):
  m=module();self.assertFalse(m.check(self.config,self.model)['editable'])
  with self.assertRaisesRegex(ValueError,'filter_editability_unverified'):m.check({**self.config,'method':'smart'},{**self.model,'layers':[{'id':2,'kind':'SmartObject','hasMask':False}]})
