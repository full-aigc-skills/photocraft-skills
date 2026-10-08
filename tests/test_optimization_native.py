"""优化候选真实原生回归：递归另存与背景滤镜保护；不是固定安装或创作接受。"""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
def workflow():
 spec=importlib.util.spec_from_file_location('optimization_workflow',ROOT/'skills/photocraft-use/scripts/workflow.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
@unittest.skipUnless(os.environ.get('CRAFT_OPTIMIZATION_NATIVE_TEST')=='1','explicit native optimization opt-in')
class OptimizationNativeTests(unittest.TestCase):
 def test_native_16_bit_source_cannot_claim_rgba8_protection(self):
  m=workflow()
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary);source=root/'sixteen';manifest=m.execute({'document':{'width':16,'height':16,'depth':16,'background':'#ffffff'},'operations':[],'exports':[{'format':'png'}]},source)
   original=m.sha(source/'project.pcraft');self.assertEqual(json.loads((source/'native.json').read_text())['depth'],16)
   with self.assertRaisesRegex(ValueError,'protected_pixel_mode_unsupported'):m.execute({'expectedProjectSha256':manifest['files']['project.pcraft'],'operations':[],'protectedRegions':[{'id':'keep','rect':[0,0,16,16]}],'exports':[{'format':'png'}]},root/'protected',source=source)
   self.assertFalse((root/'protected').exists());self.assertEqual(m.sha(source/'project.pcraft'),original)
 def test_native_batch_partial_completion_stops_following_tool(self):
  commands=workflow().load_module('commands')
  with tempfile.TemporaryDirectory() as temporary:
   output=Path(temporary)/'batch'
   plan={'schema':'craft-command-plan/v1','operations':[{'tool':'doc_new','params':{'width':32,'height':32}},{'tool':'command_batch','params':{'steps':[{'id':'layer.new.layer','params':{'name':'partial'}},{'id':'type.edit','params':{'text':'wrong kind'}}]},'as':'batch'},{'tool':'doc_save','params':{'path':{'$output':'must-not-save.pcraft'}}}]}
   receipt=commands.execute(plan,output);self.assertEqual(receipt['result'],'unknown');self.assertEqual(len(receipt['steps']),2);self.assertEqual(receipt['steps'][-1]['result']['completed'],1);self.assertEqual(receipt['steps'][-1]['result']['failed'],1);self.assertFalse((output/'must-not-save.pcraft').exists())
 def test_saved_mask_binding_and_text_layout_facts_reopen(self):
  from PIL import Image
  m=workflow()
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary);asset=root/'asset.png';Image.new('RGBA',(8,8),(200,30,15,255)).save(asset)
   plan={'document':{'width':128,'height':64,'background':'#ffffff'},'assets':{'product':{'path':str(asset),'sha256':m.sha(asset)}},'operations':[{'command':'asset.place','params':{'asset':'product','center':[40,40]},'as':'product'},{'command':'layer.layerMask.revealAll','params':{'layer':{'$ref':'product.layer'}}},{'command':'layer.layerMask.enabled','params':{'layer':{'$ref':'product.layer'},'enabled':False}},{'command':'type.create','params':{'x':8,'y':16,'text':'中A\n第二行','font':'Songti SC','size':10,'tracking':20},'as':'title'}],'assertions':[{'layer':{'$ref':'product.layer'},'hasMask':True,'maskEnabled':False,'maskLinked':True},{'layer':{'$ref':'title.layer'},'lineCount':2,'lineRanges':[[0,2],[3,6]],'tracking':20,'font':'Songti SC'}],'exports':[{'format':'png'}]}
   source=root/'source';result=m.execute(plan,source);facts=json.loads((source/'native-facts.json').read_text());self.assertFalse(facts['objects'][str(result['bindings']['product']['layer'])]['maskEnabled'])
   self.assertEqual(m.load_module('native_verify').verify(source,Path.home()/'.local/share/craft-runtimes')['result'],'PASS')
   title=result['bindings']['title']['layer'];project=m.sha(source/'project.pcraft')
   revision={'expectedProjectSha256':project,'operations':[{'command':'type.edit','params':{'layer':title,'text':'新A\n第二行'}}],'preserveObjects':{str(title):['text.text','bounds']},'assertions':[{'layer':title,'lineCount':2,'tracking':20,'size':10,'leading':'auto'}],'exports':[{'format':'png'}]}
   m.execute(revision,root/'revision',source=source);self.assertEqual(m.sha(source/'project.pcraft'),project)
   for i,assertion in enumerate([{'layer':title,'hasMask':True},{'layer':title,'lineCount':1},{'layer':title,'tracking':0},{'layer':result['bindings']['product']['layer'],'maskEnabled':True}]):
    bad={**revision,'operations':[],'assertions':[assertion]}
    with self.subTest(assertion=assertion),self.assertRaisesRegex(ValueError,'object_assertion_failed'):m.execute(bad,root/('bad'+str(i)),source=source)
 def test_missing_font_requires_explicit_accepted_substitution(self):
  m=workflow()
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary);plan={'document':{'width':64,'height':64},'operations':[{'command':'type.create','params':{'text':'标题','font':'PhotoCraft Deliberately Missing Font','size':10,'x':4,'y':20},'as':'title'}],'exports':[{'format':'png'}]}
   with self.assertRaisesRegex(ValueError,'missing_fonts'):m.execute(plan,root/'missing')
   accepted={**plan,'acceptedFontSubstitutions':{'PhotoCraft Deliberately Missing Font':'Songti SC'},'assertions':[{'layer':{'$ref':'title.layer'},'font':'Songti SC','lineCount':1}]}
   m.execute(accepted,root/'accepted');self.assertTrue((root/'accepted/font-substitutions.json').exists())
 def test_nested_text_preservation_and_recursive_layout(self):
  m=workflow()
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary);source=root/'source'
   first=m.execute({'document':{'width':64,'height':64,'background':'#ffffff'},'operations':[{'command':'type.create','params':{'x':8,'y':20,'text':'标题','font':'Songti SC','size':10,'name':'Title'},'as':'title'},{'command':'native.command','params':{'command':'layer.groupLayers','params':{'layer':{'$ref':'title.layer'},'name':'Nested'}}}], 'exports':[{'format':'png'},{'format':'psd'}]},source)
   native=json.loads((source/'native.json').read_text());objects=m.load_module('domain_assertions').index(native);title=first['bindings']['title']['layer'];self.assertIsNotNone(objects[str(title)]['_parent'])
   original=m.sha(source/'project.pcraft')
   plan={'expectedProjectSha256':original,'expectedManifestSha256':m.sha(source/'manifest.json'),'operations':[{'command':'type.edit','params':{'layer':title,'text':'新品'}}],'preserveObjects':{str(title):['text.text','bounds']},'assertions':[{'layer':title,'kind':'Type','text':'新品'}],'exports':[{'format':'png'},{'format':'psd'}]}
   m.execute(plan,root/'revised',source=source);report=json.loads((root/'revised/object-preservation.json').read_text());self.assertEqual(report['status'],'PASS');self.assertEqual(m.sha(source/'project.pcraft'),original)
   bad={**plan,'operations':[{'command':'native.command','params':{'command':'layer.ungroupLayers','params':{'layer':int(objects[str(title)]['_parent'])}}}]}
   bad.pop('assertions')
   with self.assertRaisesRegex(ValueError,'structure_changed'):m.execute(bad,root/'flattened',source=source)
   self.assertTrue((root/'flattened/failure.json').exists());self.assertEqual(m.sha(source/'project.pcraft'),original)
 def test_blur_noise_sharpen_background_preserve_product_pixels(self):
  from PIL import Image
  m=workflow()
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary);bg=root/'background.png';product=root/'product.png'
   image=Image.new('RGBA',(64,64));image.putdata([(60 if (x//4+y//4)%2 else 180,100,140,255) for y in range(64) for x in range(64)]);image.save(bg);Image.new('RGBA',(8,8),(235,30,15,255)).save(product)
   plan={'document':{'width':64,'height':64,'background':'#ffffff'},'assets':{name:{'path':str(path),'sha256':m.sha(path)} for name,path in [('background',bg),('product',product)]},'operations':[{'command':'asset.place','params':{'asset':'background','center':[32,32]},'as':'background'},{'command':'asset.place','params':{'asset':'product','center':[32,32]},'as':'product'},{'command':'type.create','params':{'x':4,'y':12,'text':'A中','font':'Songti SC','size':8},'as':'title'},{'command':'native.command','params':{'command':'layer.groupLayers','params':{'layer':{'$ref':'title.layer'},'name':'Title group'}}}],'exports':[{'format':'png'}]}
   source=root/'source';manifest=m.execute(plan,source);original=m.sha(source/'project.pcraft');target=manifest['bindings']['background']['layer']
   variant={'expectedProjectSha256':original,'operations':[{'command':'image.canvasSize','params':{'width':80,'height':80,'anchor':'center'}}],'variant':{'width':80,'height':80,'safeArea':[0,0,80,80],'roles':{'background':manifest['bindings']['background']['layer'],'product':manifest['bindings']['product']['layer'],'text':manifest['bindings']['title']['layer']}},'exports':[{'format':'png'}]}
   m.execute(variant,root/'variant',source=source);self.assertEqual(json.loads((root/'variant/layout-variant.json').read_text())['targetSize'],[80,80])
   for index,(command,params) in enumerate([('filter.blur.gaussianBlur',{'radius':1.5}),('filter.noise.addNoise',{'amount':12,'seed':4}),('filter.sharpen.sharpen',{})]):
    revision={'expectedProjectSha256':original,'operations':[{'command':'layer.select','params':{'layer':target}},{'command':'native.command','params':{'command':command,'params':params}}],'filterContract':{'target':target,'method':'raster','selection':False,'mask':False,'region':[0,0,16,16]},'protectedRegions':[{'id':'product','rect':[28,28,8,8]}],'preserveObjects':{},'exports':[{'format':'png'},{'format':'psd'}]}
    output=root/str(index);m.execute(revision,output,source=source);report=json.loads((output/'filter-contract.json').read_text());self.assertGreater(report['steps'][0]['pixels']['changedPixels'],0);self.assertFalse(report['steps'][0]['context']['editable']);self.assertEqual(m.sha(source/'project.pcraft'),original)
