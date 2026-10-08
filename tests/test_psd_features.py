import importlib.util
from pathlib import Path
import unittest
SOURCE=Path(__file__).resolve().parents[1]/'skills/photocraft-use/scripts/psd_features.py'
def module():
 s=importlib.util.spec_from_file_location('psd_features',SOURCE);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class PsdFeatureTests(unittest.TestCase):
 def test_same_layer_count_cannot_hide_type_or_mask_loss(self):
  native={'layers':[{'id':1,'name':'Title','kind':'Type','text':{'text':'中文','font':'Arial'},'hasMask':True}]}
  psd={'layers':[{'id':99,'name':'Title','kind':'Pixel','hasMask':False}]}
  matrix=module().assess(native,psd)
  self.assertEqual(matrix['features']['0:text']['status'],'lost');self.assertEqual(matrix['features']['0:mask']['status'],'lost');self.assertFalse(matrix['completeFidelity'])
 def test_observed_text_can_be_retained_but_unreported_effect_remains_unknown(self):
  native={'layers':[{'id':1,'kind':'Type','name':'Title','text':{'text':'A','font':'Arial'}}]};psd={'layers':[{'id':9,'kind':'Type','name':'Title','text':{'text':'A','font':'Arial'}}]}
  matrix=module().assess(native,psd,used_effects=True)
  self.assertEqual(matrix['features']['0:text']['status'],'retained');self.assertEqual(matrix['features']['effects']['status'],'unknown');self.assertFalse(matrix['completeFidelity'])
 def test_nested_order_name_and_property_degradation_are_recorded(self):
  a={'layers':[{'id':1,'kind':'Group','name':'Group','children':[{'id':2,'kind':'Type','name':'Title','text':{'text':'A','tracking':2}}]}]};b={'layers':[{'id':7,'kind':'Group','name':'Group','children':[{'id':8,'kind':'Type','name':'Title','text':{'text':'A','tracking':0}}]}]}
  self.assertEqual(module().assess(a,b)['features']['0/0:text']['status'],'degraded')
