"""失败暂存生命周期：保全、目录竞争、成功清理及诊断失败不遮蔽原异常。"""
import importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];DOMAIN=json.loads((ROOT/'skill-suite.json').read_text())['pluginId']
class PreservedStageTests(unittest.TestCase):
 def setUp(self):
  spec=importlib.util.spec_from_file_location('preservation',ROOT/'skills'/(DOMAIN+'-use')/'scripts/preserved_stage.py');self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m)
 def test_unknown_error_keeps_original_paths_and_successful_operations(self):
  with tempfile.TemporaryDirectory() as tmp:
   output=Path(tmp)/'delivery';state={'operations':[{'command':'created','result':{'id':7}}]}
   with self.assertRaisesRegex(RuntimeError,'outcome_unknown:'):
    with self.m.preserved_stage(output,'.stage-',state) as directory:
     stage=Path(directory);(stage/'checkpoint.native').write_bytes(b'original');raise RuntimeError('outcome_unknown: reply_missing')
   failure=json.loads((output/'failure.json').read_text());self.assertEqual((output/failure['stage']).resolve(),stage.resolve());self.assertEqual(failure['completedOperations'],1);self.assertEqual(json.loads((stage/'recovery-operations.json').read_text()),state['operations']);self.assertEqual((stage/'checkpoint.native').read_bytes(),b'original');self.assertFalse(failure['replayAllowed']);self.assertEqual(failure['outcome'],'outcome_unknown')
 def test_success_cleans_only_stage(self):
  with tempfile.TemporaryDirectory() as tmp:
   output=Path(tmp)/'delivery'
   with self.m.preserved_stage(output,'.stage-') as directory:
    stage=Path(directory);(stage/'scratch').write_text('scratch');output.mkdir();(output/'project').write_text('final')
   self.assertFalse(stage.exists());self.assertEqual((output/'project').read_text(),'final');self.assertFalse((output/'failure.json').exists())
 def test_successful_stage_rename_retains_delivery(self):
  with tempfile.TemporaryDirectory() as tmp:
   output=Path(tmp)/'delivery'
   with self.m.preserved_stage(output,'.stage-') as directory:
    stage=Path(directory);(stage/'project').write_text('final');stage.rename(output)
   self.assertEqual((output/'project').read_text(),'final')
 def test_competing_output_is_never_overwritten(self):
  with tempfile.TemporaryDirectory() as tmp:
   output=Path(tmp)/'delivery'
   with self.assertRaisesRegex(ValueError,'target_conflict'):
    with self.m.preserved_stage(output,'.stage-') as directory:
     stage=Path(directory);(stage/'project').write_text('native');output.mkdir();(output/'failure.json').write_text('user');raise ValueError('target_conflict')
   self.assertEqual((output/'failure.json').read_text(),'user');self.assertTrue((stage/'failure.json').is_file());self.assertTrue((stage/'project').is_file())
 def test_external_symlink_is_not_followed(self):
  with tempfile.TemporaryDirectory() as tmp:
   output=Path(tmp)/'delivery';other=Path(tmp)/'user';other.mkdir()
   with self.assertRaisesRegex(ValueError,'target_conflict'):
    with self.m.preserved_stage(output,'.stage-') as directory:
     stage=Path(directory);(stage/'project').write_text('native');output.symlink_to(other,target_is_directory=True);(stage/'linked').symlink_to(other,target_is_directory=True);raise ValueError('target_conflict')
   self.assertFalse((other/'failure.json').exists());failure=json.loads((stage/'failure.json').read_text());self.assertNotIn('linked',failure['files'])
 def test_owned_partial_output_gets_recovery_record(self):
  with tempfile.TemporaryDirectory() as tmp:
   output=Path(tmp)/'delivery';state={}
   with self.assertRaisesRegex(ValueError,'render_failed'):
    with self.m.preserved_stage(output,'.stage-',state) as directory:
     stage=Path(directory);(stage/'project').write_text('native');self.m.claim_output(output,state);(output/'partial').write_text('partial');raise ValueError('render_failed')
   self.assertEqual((output/'partial').read_text(),'partial');self.assertEqual(json.loads((output/'failure.json').read_text())['outcome'],'failed');self.assertTrue(stage.exists())
 def test_diagnostic_failure_never_masks_original_or_deletes_stage(self):
  with tempfile.TemporaryDirectory() as tmp:
   output=Path(tmp)/'delivery'
   with patch.object(self.m,'_write_record',side_effect=PermissionError('read only')):
    with self.assertRaisesRegex(RuntimeError,'native_unknown'):
     with self.m.preserved_stage(output,'.stage-') as directory:
      stage=Path(directory);(stage/'project').write_text('native');raise RuntimeError('native_unknown')
   self.assertEqual((stage/'project').read_text(),'native')

 def test_replaced_owned_output_is_not_overwritten(self):
  with tempfile.TemporaryDirectory() as tmp:
   output=Path(tmp)/'delivery';state={}
   with self.assertRaisesRegex(ValueError,'directory_replaced'):
    with self.m.preserved_stage(output,'.stage-',state) as directory:
     stage=Path(directory);(stage/'project').write_text('native');self.m.claim_output(output,state);output.rename(Path(tmp)/'old-owned');output.mkdir();(output/'failure.json').write_text('user');raise ValueError('directory_replaced')
   self.assertEqual((output/'failure.json').read_text(),'user');self.assertTrue((stage/'failure.json').is_file())
