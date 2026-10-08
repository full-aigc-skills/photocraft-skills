"""版本化有限 binary64 计划身份，历史格式只读兼容。"""
import hashlib,importlib.util,json,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('tested_plan_identity',Path(__file__).resolve().parents[1]/'skills/photocraft-use/scripts/plan_identity.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class PlanIdentityTests(unittest.TestCase):
 def test_numeric_representation_is_semantic_and_type_tags_do_not_collide(self):
  sha=lambda value:module.sha(value,module.ALGORITHM)
  self.assertEqual(sha(100),sha(100.0));self.assertEqual(sha(-0.0),sha(0));self.assertEqual(module.tagged(0.000001),['number','3eb0c6f7a0b5ed8d'])
  values=[1,True,'1',['number','3ff0000000000000'],{'number':'3ff0000000000000'},None,'null'];self.assertEqual(len({sha(v) for v in values}),len(values))
 def test_unicode_keys_follow_utf16_and_surrogates_have_deterministic_identity(self):
  tagged=module.tagged({'\ue000':2,'😀':1});self.assertEqual([row[0] for row in tagged[1]],['😀','\ue000']);self.assertEqual(module.sha({'a':'\ud800'},module.ALGORITHM),'f653f701a3cc2109becce2f8205ca6b3570a276753b4dda3decc0fcb883a8e67')
 def test_unknown_algorithms_nonfinite_and_non_json_objects_are_refused(self):
  with self.assertRaises(ValueError):module.sha({},'unknown')
  for value in [float('inf'),float('-inf'),float('nan'),10**400,{1:'non-string key'},object()]:
   with self.subTest(value=type(value).__name__),self.assertRaises(ValueError):module.sha(value,module.ALGORITHM)
 def test_legacy_hash_remains_available_without_algorithm_metadata(self):
  plan={'operations':[],'x':0.000001};old=hashlib.sha256(json.dumps(plan,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest();self.assertEqual(module.sha(plan),old);self.assertNotEqual(module.sha(plan,module.ALGORITHM),old)
