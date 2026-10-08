import importlib.util
from pathlib import Path
import tempfile
import unittest
import zipfile
import json
ROOT=Path(__file__).resolve().parents[1]/'skills/photocraft-use/scripts'
def load(name):
 s=importlib.util.spec_from_file_location('facts_'+name,ROOT/(name+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class NativeFactsTests(unittest.TestCase):
 def test_mask_is_bound_to_saved_layer_and_enabled_is_not_inferred(self):
  facts=load('native_facts');model={'layers':[{'id':1,'kind':'Pixel','hasMask':True},{'id':2,'kind':'Pixel','hasMask':False}]}
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'project.pcraft'
   with zipfile.ZipFile(path,'w') as archive:archive.writestr('manifest.json',json.dumps({'format_version':1,'document':{'layers':[{'id':1,'content':{'kind':'raster'},'mask':{'surface':{'format':{'mode':'Grayscale','sample':'U8','alpha':False},'default':'00','tiles':[]},'enabled':False,'linked':True,'density':1,'feather':0}},{'id':2,'content':{'kind':'raster'},'mask':None}]}}))
   report=facts.collect(path,model,lambda *_:self.fail('pixel document queried text'))
   assertions=load('domain_assertions');assertions.assert_objects(model,[{'layer':1,'maskEnabled':False,'maskLinked':True}],report)
   with self.assertRaisesRegex(ValueError,'object_assertion_failed'):assertions.assert_objects(model,[{'layer':2,'hasMask':True}],report)
   with self.assertRaisesRegex(ValueError,'object_assertion_failed'):assertions.assert_objects(model,[{'layer':1,'maskEnabled':True}],report)
 def test_mask_surface_changes_are_not_hidden_by_equal_enabled_flags(self):
  facts=load('native_facts');model={'layers':[{'id':1,'kind':'Pixel','hasMask':True}]}
  with tempfile.TemporaryDirectory() as tmp:
   reports=[]
   for index in range(2):
    path=Path(tmp)/str(index);mask={'surface':{'format':{'mode':'Grayscale','sample':'U8','alpha':False},'default':'00','tiles':[{'tx':0,'ty':0,'hash':'a'*64}]},'enabled':True,'linked':True,'density':1,'feather':0}
    with zipfile.ZipFile(path,'w') as archive:
     archive.writestr('manifest.json',json.dumps({'format_version':1,'document':{'layers':[{'id':1,'content':{'kind':'raster'},'mask':mask}]}}));archive.writestr('tiles/'+('a'*64)+'.zst',b'mask-'+str(index).encode())
    reports.append(facts.collect(path,model,lambda *_:None))
   with self.assertRaisesRegex(ValueError,'native_facts_object_changed: 1: maskSurfaceSha256'):facts.preserve(*reports,{})
 def test_exact_text_layout_and_tracking_reject_changed_runs(self):
  m=load('domain_assertions');model={'layers':[{'id':1,'kind':'Type','text':{'text':'中\nA'}}]};facts={'objects':{'1':{'textInfo':{'lines':[{'start':0,'end':1},{'start':2,'end':3}],'runs':[{'style':{'tracking':20,'font_family':'Songti SC'}}],'orientation':'Horizontal'}}}}
  m.assert_objects(model,[{'layer':1,'lineCount':2,'lineRanges':[[0,1],[2,3]],'tracking':20,'font':'Songti SC'}],facts)
  for assertion in [{'lineCount':1},{'lineRanges':[[0,3]]},{'tracking':0},{'font':'missing'}]:
   with self.subTest(assertion=assertion),self.assertRaisesRegex(ValueError,'object_assertion_failed'):m.assert_objects(model,[{'layer':1,**assertion}],facts)
  with self.assertRaisesRegex(ValueError,'layout_metric_unavailable'):m.assert_objects(model,[{'layer':1,'lineCount':2}])
  with self.assertRaisesRegex(ValueError,'layout_metric_unavailable: glyphCoverage'):m.assert_objects(model,[{'layer':1,'glyphCoverage':True}],facts)
