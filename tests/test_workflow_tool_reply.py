"""真实stdio子进程：公共工作流使用的Session必须拒绝异常工具结构。"""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
DOMAIN=json.loads((ROOT/'skill-suite.json').read_text())['pluginId']
class WorkflowToolReplyTests(unittest.TestCase):
 def session(self):
  p=ROOT/'skills'/(DOMAIN+'-use')/'scripts/mcp_session.py'
  spec=importlib.util.spec_from_file_location('workflow_session',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m.Session
 def test_bad_tool_results_are_unknown_without_python_type_errors(self):
  values=[None,[],{}, {'content':None},{'content':[None]}, {'content':[{'type':'text'}]}, {'content':[{'type':'text','text':3}]},{'content':[],'isError':'false'}]
  for value in values:
   with self.subTest(value=value):
    child="import sys,json\nfor line in sys.stdin:\n r=json.loads(line)\n if 'id' in r: print(json.dumps({'jsonrpc':'2.0','id':r['id'],'result':json.loads(sys.argv[1]) if r['method']=='tools/call' else {}}),flush=True)\n"
    with self.session()([sys.executable,'-I','-B','-u','-c',child,json.dumps(value)]) as session:
     with self.assertRaisesRegex(RuntimeError,'outcome_unknown: invalid_tool_reply'):
      session.request('tools/call',{'name':'test_tool','arguments':{}})
 def test_valid_semantic_error_remains_a_known_reply(self):
  child="import sys,json\nfor line in sys.stdin:\n r=json.loads(line)\n if 'id' in r: print(json.dumps({'jsonrpc':'2.0','id':r['id'],'result':{'isError':True,'content':[{'type':'text','text':'known error'}]} if r['method']=='tools/call' else {}}),flush=True)\n"
  with self.session()([sys.executable,'-I','-B','-u','-c',child]) as session:
   self.assertTrue(session.request('tools/call',{'name':'test_tool','arguments':{}})['isError'])
