"""智能对象公开映射必须拒绝私有路径和不完整目标。"""
import importlib.util
from pathlib import Path
import unittest
P=Path(__file__).resolve().parents[1]/'skills/photocraft-use/scripts/workflow.py'
class SmartWorkflowTests(unittest.TestCase):
 def setUp(self):
  s=importlib.util.spec_from_file_location('smart_workflow',P);self.m=importlib.util.module_from_spec(s);s.loader.exec_module(self.m)
 def test_registered_smart_operations_accepted(self):
  for command,params in [('asset.placeSmart',{'asset':'product','center':[32,32]}),('layer.smartObjects.convertToSmartObject',{'layer':{'$ref':'product.layer'}}),('layer.smartObjects.replaceContents',{'layer':1,'asset':'product'}),('layer.smartObjects.relinkToFile',{'layer':1,'asset':'product'}),('layer.smartObjects.convertToEmbedded',{'layer':1})]:self.m.validate({'operations':[{'command':command,'params':params}]})
 def test_private_path_unknown_fields_and_missing_layer_rejected(self):
  for params in [{'layer':1,'path':'/outside.png'},{'asset':'product'},{'layer':True,'asset':'product'},{'layer':1,'asset':'product','bad':1}]:
   with self.assertRaisesRegex(ValueError,'invalid_smart_params'):self.m.validate({'operations':[{'command':'layer.smartObjects.replaceContents','params':params}]})
 def test_invalid_place_geometry_rejected(self):
  for params in [{'asset':'product','center':[1,float('nan')]},{'asset':'product','scale':0},{'asset':'product','fit':1}]:
   with self.assertRaisesRegex(ValueError,'invalid_smart_params'):self.m.validate({'operations':[{'command':'asset.placeSmart','params':params}]})
if __name__=='__main__':unittest.main()
