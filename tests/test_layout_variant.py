"""尺寸变体必须绑定实际保存图层及原生尺寸操作结果。"""
import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
class LayoutVariantTests(unittest.TestCase):
 def setUp(self):
  spec=importlib.util.spec_from_file_location('layout',ROOT/'skills/photocraft-use/scripts/layout_variant.py')
  self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m)
  self.config={'width':120,'height':80,'safeArea':[10,10,100,60],'roles':{'background':1,'product':2,'text':3}}
  self.before={'width':100,'height':100,'layers':[{'id':1,'kind':'Pixel','bounds':[0,0,100,100],'visible':True},{'id':2,'kind':'Pixel','bounds':[20,30,20,20],'visible':True},{'id':3,'kind':'Type','bounds':[20,20,30,10],'visible':True,'text':{'text':'NOVA','font':'Arial'}}]}
  import copy
  self.after=copy.deepcopy(self.before);self.after.update(width=120,height=80)
  for layer in self.after['layers']:layer['bounds'][0]+=10;layer['bounds'][1]-=10
  self.steps=[{'command':'image.canvasSize','before':[100,100],'result':{'width':120,'height':80,'offset':[10,-10]}}]
 def test_records_actual_crop_padding_and_role_ids(self):
  report=self.m.assess(self.config,self.before,self.after,self.steps,{})
  self.assertEqual(report['steps'][0]['crop'],{'left':0,'top':10,'right':0,'bottom':10})
  self.assertEqual(report['steps'][0]['padding'],{'left':10,'top':0,'right':10,'bottom':0})
  self.assertEqual(report['roles']['text']['id'],3)
 def test_rejects_target_mismatch(self):
  self.after['width']=121
  with self.assertRaisesRegex(ValueError,'variant_size_mismatch'):self.m.assess(self.config,self.before,self.after,self.steps,{})
 def test_rejects_outside_safe_area(self):
  self.after['layers'][1]['bounds']=[0,0,20,20]
  with self.assertRaisesRegex(ValueError,'variant_safe_area_violation'):self.m.assess(self.config,self.before,self.after,self.steps,{})
 def test_rejects_flattened_role(self):
  self.after['layers'][2]['kind']='Pixel'
  with self.assertRaisesRegex(ValueError,'variant_role_changed'):self.m.assess(self.config,self.before,self.after,self.steps,{})
 def test_rejects_duplicate_role_ids(self):
  self.config['roles']['text']=2
  with self.assertRaisesRegex(ValueError,'variant_role_identity'):self.m.assess(self.config,self.before,self.after,self.steps,{})
 def test_rejects_invalid_schema(self):
  for config in [dict(self.config,extra=1),dict(self.config,width=True),dict(self.config,safeArea=[0,0,121,80])]:
   with self.assertRaises(ValueError):self.m.validate(config)

class VariantWorkflowPreflightTests(unittest.TestCase):
 def test_invalid_variant_is_rejected_before_runtime_or_source_access(self):
  spec=importlib.util.spec_from_file_location('variant_workflow',ROOT/'skills/photocraft-use/scripts/workflow.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  plan={'operations':[],'variant':{'width':120,'height':80,'safeArea':[0,0,121,80],'roles':{'background':1,'product':2,'text':3}}}
  with self.assertRaisesRegex(ValueError,'invalid_variant_safe_area'):module.validate(plan)

if __name__=='__main__':unittest.main()
