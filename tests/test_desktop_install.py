"""独立技能桌面安装必须锁定官方制品并在失败时拒绝写入。"""
import importlib.util,json,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(skill):
 spec=importlib.util.spec_from_file_location('craft_desktop',skill/'scripts/desktop.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
class DesktopInstallContract(unittest.TestCase):
 def test_every_skill_has_own_pinned_installer_and_guide(self):
  for s in (ROOT/'skills').iterdir():
   if not (s/'SKILL.md').exists():continue
   m=load(s);lock=json.loads((s/'scripts/desktop.lock.json').read_text());self.assertEqual(m.validate(lock)['version'],'0.2.0');self.assertIn('references/desktop-install.md',(s/'SKILL.md').read_text());self.assertTrue((s/'references/desktop-install.md').exists())
 def test_untrusted_url_and_platform_are_rejected(self):
  s=next(s for s in (ROOT/'skills').iterdir() if (s/'SKILL.md').exists());m=load(s);lock=json.loads((s/'scripts/desktop.lock.json').read_text());bad=json.loads(json.dumps(lock));bad['url']='https://example.com/app.dmg'
  with self.assertRaises(ValueError):m.validate(bad)
  with tempfile.TemporaryDirectory() as td:
   home=Path(td)/'runtime'
   with self.assertRaisesRegex(ValueError,'unsupported_platform'):m.install(lock,home,platform_key='linux-x86_64')
   self.assertFalse(home.exists())
 def test_bad_archive_does_not_create_install(self):
  s=next(s for s in (ROOT/'skills').iterdir() if (s/'SKILL.md').exists());m=load(s);lock=json.loads((s/'scripts/desktop.lock.json').read_text())
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);archive=root/'bad.dmg';archive.write_bytes(b'wrong bytes');home=root/'runtime'
   with self.assertRaisesRegex(ValueError,'archive_identity_mismatch'):m.install(lock,home,archive=archive,platform_key='darwin-arm64')
   self.assertFalse((home/(lock['domain']+'-desktop')/lock['version']).exists())

import hashlib,os,shutil,subprocess,sys

def hashes(root):return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
@unittest.skipUnless(os.environ.get('CRAFT_DESKTOP_FIRST_USE')=='1','explicit public DMG install opt-in')
class DesktopPublicFirstUse(unittest.TestCase):
 def test_independent_cold_install_reuse_and_mutation_rejection(self):
  original=Path(os.environ['CRAFT_DESKTOP_SKILL']);before=hashes(original)
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);skill=root/'.agents/skills'/original.name;shutil.copytree(original,skill,ignore=shutil.ignore_patterns('__pycache__'));identity=hashes(skill);home=root/'empty-runtime';self.assertFalse(home.exists());env=dict(os.environ,PATH='/usr/bin:/bin')
   def run(ok=True):
    argv=[sys.executable,'-I','-B',str(skill/'scripts/desktop.py'),'install','--runtime-home',str(home)];r=subprocess.run(argv,capture_output=True,text=True,env=env,timeout=420)
    if not ok:self.assertNotEqual(r.returncode,0);self.assertIn('desktop_install_mutated',r.stdout+r.stderr);return
    self.assertEqual(r.returncode,0,r.stdout+r.stderr);return json.loads(r.stdout)
   first=run();self.assertFalse(first['reused']);self.assertEqual(first['version'],'0.2.0');self.assertEqual(hashlib.sha256(Path(first['executable']).read_bytes()).hexdigest(),first['binarySha256']);app=Path(first['app']);snapshot=hashes(app);second=run();self.assertTrue(second['reused']);self.assertEqual(first['binarySha256'],second['binarySha256']);self.assertEqual(snapshot,hashes(app));receipt=app.parent/'receipt.json';stored=json.loads(receipt.read_text());stored['files']['FAKE']={'sha256':'0'*64};receipt.write_text(json.dumps(stored));run(False);self.assertEqual(snapshot,hashes(app));self.assertEqual(before,hashes(original));self.assertEqual(identity,hashes(skill));self.assertFalse(list(skill.rglob('*.pyc')))
   if os.environ.get('CRAFT_DESKTOP_REPORT'):
    Path(os.environ['CRAFT_DESKTOP_REPORT']).write_text(json.dumps({'schema':'craft-desktop-public-install-first-use/v1','result':'PASS','skill':original.name,'version':first['version'],'binarySha256':first['binarySha256'],'emptyPublicRuntime':True,'reusedWithoutChanges':True,'receiptMutationRejected':True,'appPreservedAfterRejection':True,'skillIdentityUnchanged':True,'applicationLaunched':False,'scope':'public fixed DMG independent single-skill installer; not GUI launch, bridge/editing or fullV1'},indent=2)+'\n')
