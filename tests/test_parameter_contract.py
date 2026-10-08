"""公开参数约定必须在安装之前和引用解析之后按字段位置校验。"""
import importlib.util
from pathlib import Path
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
def load(name):
 s=importlib.util.spec_from_file_location('parameter_'+name,ROOT/'skills/photocraft-use/scripts'/f'{name}.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class ParameterPreflightTests(unittest.TestCase):
 def test_mcp_tools_use_fixed_schema_before_install_and_after_resolution(self):
  commands=load('commands')
  for tool,params,field in [('doc_new',{'width':'32'},'width'),('doc_new',{'name':42},'name'),('doc_export',{'path':42},'path'),('doc_export',{'quality':256},'quality'),('doc_open',{'pth':'x'},'path')]:
   with self.subTest(tool=tool),self.assertRaisesRegex(ValueError,'params.'+field):commands.validate({'schema':'craft-command-plan/v1','operations':[{'tool':tool,'params':params}]})
  commands.validate_tool_parameters('doc_new',{'name':None,'width':32})
  with self.assertRaisesRegex(ValueError,'parameter_type'):commands.validate_tool_parameters('doc_open',{'path':12},resolved=True)
 def test_document_nested_settings_fail_before_installer(self):
  workflow=load('workflow')
  for setting in ({'name':42},{'background':False},{'depth':'8'}):
   with self.subTest(setting=setting),self.assertRaisesRegex(ValueError,'parameter_type'):workflow.preflight({'document':{'width':32,'height':32,**setting},'operations':[]})
 def test_asset_wrapper_and_final_assertion_references_are_preflighted(self):
  workflow=load('workflow')
  for params in [{'asset':'product','center':'bad'},{'asset':'product','center':[True,2]},{'asset':'product','name':42}]:
   plan={'document':{'width':32,'height':32},'operations':[{'command':'asset.place','params':params}]}
   with self.subTest(params=params),self.assertRaisesRegex(ValueError,'parameter_type'):workflow.validate(plan,check_references=False)
  with self.assertRaisesRegex(ValueError,'reference'):
   workflow.preflight({'document':{'width':32,'height':32},'operations':[],'assertions':[{'layer':{'$ref':'missing.layer'},'kind':'Type'}]})
 def test_batch_cannot_bypass_native_parameter_checks(self):
  commands=load('commands')
  for step in [{'id':42},{'id':'not.a.command'},{'id':'type.create','params':{'text':12}},{'id':'layer.new.layer','unexpected':True}]:
   with self.subTest(step=step),self.assertRaises(ValueError):commands.validate_tool_parameters('command_batch',{'steps':[step]})
 def test_partial_batch_is_not_a_successful_alias(self):
  commands=load('commands')
  with self.assertRaisesRegex(RuntimeError,'outcome_unknown'):
   commands.validate_tool_reply('command_batch',{'completed':1,'failed':1,'results':[{'ok':True,'result':{}},{'ok':False,'error':'failed'}]},{'steps':[{},{}]})
 def test_known_type_range_and_unknown_fields_are_rejected(self):
  commands=load('commands')
  for command,params,field in [('type.create',{'text':42},'text'),('type.setStyle',{'size':'large'},'size'),('select.rect',{'width':-1},'width'),('select.rect',{'ellipse':'true'},'ellipse'),('layer.select',{'layer':True},'layer'),('filter.blur.gaussianBlur',{'raduis':3},'raduis')]:
   with self.subTest(command=command,field=field),self.assertRaisesRegex(ValueError,r'operations\[0\].params.'+field):commands.validate({'schema':'craft-command-plan/v1','operations':[{'command':command,'params':params}]})
 def test_normal_workflow_and_native_gateway_share_zero_install_preflight(self):
  m=load('workflow');original=m.load_module
  def checked(name):
   if name=='bootstrap':self.fail('invalid parameters reached install')
   return original(name)
  m.load_module=checked
  for operation in [{'command':'type.create','params':{'text':12}},{'command':'native.command','params':{'command':'select.rect','params':{'width':-1}}}]:
   with tempfile.TemporaryDirectory() as temp,self.assertRaisesRegex(ValueError,'parameter_'):
    m.execute({'document':{'width':32,'height':32},'operations':[operation]},Path(temp)/'out')
 def test_native_reply_reference_is_type_checked_before_next_edit(self):
  commands=load('commands')
  with self.assertRaisesRegex(ValueError,'parameter_type'):
   commands.validate_parameters('type.edit',{'text':12},'$.operations[2].params',resolved=True)
 def test_finite_numeric_check_never_leaks_integer_conversion_overflow(self):
  with self.assertRaisesRegex(ValueError,'parameter_type'):load('commands').validate_parameters('type.setStyle',{'size':10**1000})
 def test_inclusive_range_marker_is_not_mistaken_for_default_assignment(self):
  contract=load('parameter_contract');contract.validate_value('0..=100=50',100,'$.range')
  for value in ('large',101):
   with self.assertRaisesRegex(ValueError,'parameter_type|parameter_range'):contract.validate_value('0..=100=50',value,'$.range')
 def test_legal_optional_values_and_dynamic_references_remain_compatible(self):
  commands=load('commands')
  for command,params in [('type.create',{'text':'中A','font':'Arial','size':12,'x':8,'y':20}),('layer.select',{'layer':{'$ref':'title.layer'}}),('paint.stroke',{'points':[[0,0],[1,2,.5]],'target':{'channel':1}}),('layer.setProps',{'locks':{'pixels':True},'channels':[True,False,True]})]:
   commands.validate_parameters(command,params,'$.operations[0].params')
