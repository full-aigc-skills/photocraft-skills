import importlib.util
import json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]/'skills/photocraft-use/scripts'
def load(name):
 spec=importlib.util.spec_from_file_location('json_test_'+name,ROOT/(name+'.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
class StrictJSONPaths(unittest.TestCase):
 def test_duplicate_and_nonfinite_numbers_have_exact_paths(self):
  parse=load('commands').reply_json
  for text,path in [('{"operations":[{"params":{"text":"a","text":"b"}}]}',r'\$\.operations\[0\]\.params.text'),('{"items":[0,1e999]}',r'\$\.items\[1\]'),('{"x":NaN}',r'\$\.x')]:
   with self.subTest(text=text),self.assertRaisesRegex(ValueError,path):parse(text)
 def test_syntax_errors_remain_decode_errors_for_plain_tool_text(self):
  parse=load('commands').reply_json
  for text in ['\u00a0{}','[1,]','{"x":01}','{} trailing']:
   with self.subTest(text=text),self.assertRaises(json.JSONDecodeError):parse(text)
  self.assertEqual(parse(' \r\n{"中":[true,null,"\\u4e2d"]}'),{'中':[True,None,'中']})
 def test_mcp_and_delivery_share_strict_parser(self):
  with self.assertRaisesRegex(ValueError,r'\$\.x.y'):load('mcp_session').strict_json(b'{"x":{"y":1,"y":2}}')
