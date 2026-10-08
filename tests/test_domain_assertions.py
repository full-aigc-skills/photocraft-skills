import copy
import importlib.util
from pathlib import Path
import unittest
SCRIPTS=Path(__file__).resolve().parents[1]/'skills/photocraft-use/scripts'
def module():
 spec=importlib.util.spec_from_file_location('domain_assertions',SCRIPTS/'domain_assertions.py');value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
class DomainAssertionsTests(unittest.TestCase):
 def setUp(self):
  self.before={'layers':[{'id':1,'kind':'Group','name':'group','visible':True,'children':[{'id':2,'kind':'Type','name':'title','visible':True,'bounds':[2,2,12,8],'text':{'text':'旧标题','font':'Arial','size':8}},{'id':3,'kind':'Pixel','name':'product','visible':True,'bounds':[2,12,8,8],'hasMask':True}]}]}
 def test_recursive_same_name_kind_parent_order_and_visibility(self):
  m=module();m.compare(self.before,copy.deepcopy(self.before),{})
  for mutate in ('flatten','parent','order','kind','visible'):
   after=copy.deepcopy(self.before)
   if mutate=='flatten':after['layers']=[{'id':1,'kind':'Pixel','name':'group'}]
   elif mutate=='parent':after['layers'].append(after['layers'][0]['children'].pop())
   elif mutate=='order':after['layers'][0]['children'].reverse()
   elif mutate=='kind':after['layers'][0]['children'][0]['kind']='Pixel'
   else:after['layers'][0]['children'][1]['visible']=False
   with self.subTest(mutate=mutate),self.assertRaisesRegex(ValueError,'object_changed|structure_changed'):m.compare(self.before,after,{})
 def test_target_text_only_and_missing_metrics_refuse_exact_claim(self):
  m=module();after=copy.deepcopy(self.before);after['layers'][0]['children'][0]['text']['text']='新标题'
  m.compare(self.before,after,{'2':['text.text']})
  after['layers'][0]['children'][1]['hasMask']=False
  with self.assertRaisesRegex(ValueError,'object_changed'):m.compare(self.before,after,{'2':['text.text']})
  with self.assertRaisesRegex(ValueError,'layout_metric_unavailable'):m.assert_objects(self.before,[{'layer':2,'text':'旧标题','noOverflow':True}])
 def test_mask_and_bounds_must_be_observed_not_inferred(self):
  m=module();m.assert_objects(self.before,[{'layer':3,'kind':'Pixel','hasMask':True,'visible':True,'within':[0,0,32,32]}])
  with self.assertRaisesRegex(ValueError,'object_assertion_failed'):m.assert_objects(self.before,[{'layer':3,'hasMask':False}])
  with self.assertRaisesRegex(ValueError,'object_assertion_failed'):m.assert_objects(self.before,[{'layer':2,'within':[0,0,5,5]}])
 def test_duplicate_ids_refused(self):
  m=module();self.before['layers'].append({'id':3,'kind':'Pixel'})
  with self.assertRaisesRegex(ValueError,'duplicate_layer_identity'):m.index(self.before)

class EditableCountTests(unittest.TestCase):
 def test_functional_adjustment_counts_without_pixel_bounds_empty_pixel_does_not(self):
  m=module();model={'layers':[{'id':1,'kind':'Group','children':[]},{'id':2,'kind':'Pixel','bounds':[0,0,0,0]},{'id':3,'kind':'Adjustment','bounds':[0,0,0,0],'adjustment':{'BrightnessContrast':{'brightness':30}}}]}
  self.assertEqual(m.editable_count(model),1)
