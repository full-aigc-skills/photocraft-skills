"""单技能公开首次使用：局部修改保护区域；只使用标准库。"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
ROOT=Path(__file__).resolve().parents[1]
@unittest.skipUnless(os.environ.get('CRAFT_PROTECTED_FIRST_USE')=='1','requires declared native online first use')
class ProtectedFirstUse(unittest.TestCase):
 def test_public_skill_refuses_protected_changes_and_preserves_source(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);source=Path(os.environ.get('CRAFT_INSTALLED_PROTECTED_SKILL_ROOT',ROOT/'skills/photocraft-cli-masks'));skill=root/'only-mask-skill';shutil.copytree(source,skill,ignore=shutil.ignore_patterns('__pycache__'))
   def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
   image=root/'product.png';raw=(b'\0'+bytes([233,99,64,255])*120)*160;image.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',120,160,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b''))
   environment={**os.environ,'PATH':'/usr/bin:/bin'};environment.pop('CRAFT_RUNTIME_HOME',None);runtime=root/'runtime'
   def run(plan,output,source_project=None,asset=False):
    file=root/(output.name+'.json');file.write_text(json.dumps(plan));args=[sys.executable,'-I','-B',str(skill/'scripts/workflow.py'),str(file),'--output',str(output),'--runtime-home',str(runtime)]
    if source_project:args.extend(['--source',str(source_project)])
    if asset:args.extend(['--asset','product='+str(image)])
    return subprocess.run(args,capture_output=True,text=True,env=environment,timeout=180)
   plan=json.loads((skill/'examples/poster-plan.json').read_text());original=root/'original';first=run(plan,original,asset=True);self.assertEqual(first.returncode,0,first.stdout+first.stderr);manifest=json.loads(first.stdout)
   files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in original.iterdir() if p.is_file()}
   revision={'expectedProjectSha256':manifest['files']['project.pcraft'],'minimumLayers':4,'operations':[{'command':'type.edit','params':{'layer':{'$ref':'headline.layer'},'text':'NOVA PLUS'}}],'exports':[{'format':'png'}],'protectedRegions':[{'id':'header','rect':[0,0,320,100]}]}
   rejected=root/'rejected';bad=run(revision,rejected,original);self.assertEqual(bad.returncode,1,bad.stdout+bad.stderr);self.assertIn('protected_region_changed',bad.stdout);self.assertFalse(rejected.exists())
   self.assertEqual(files,{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in original.iterdir() if p.is_file()})
   revision['protectedRegions']=[{'id':'product-and-background','rect':[0,100,320,300]}];updated=root/'updated';good=run(revision,updated,original);self.assertEqual(good.returncode,0,good.stdout+good.stderr)
   report=json.loads((updated/'pixel-protection.json').read_text());self.assertEqual(report['regions'][0]['changedPixels'],0);self.assertEqual(report['regions'][0]['beforeSha256'],report['regions'][0]['afterSha256']);new_manifest=json.loads(good.stdout)
   self.assertIn('pixel-protection.json',new_manifest['files']);self.assertEqual(new_manifest['sourceProjectSha256'],manifest['files']['project.pcraft'])
   self.assertEqual(files,{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in original.iterdir() if p.is_file()});self.assertFalse(list(skill.rglob('*.pyc')))
   if os.environ.get('CRAFT_PROTECTED_EVIDENCE_FILE'):
    evidence={'schema':'photocraft-protected-first-use-evidence/v1','python':sys.version.split()[0],'scope':'single copied skill, fresh default online native install and system-only PATH; exact PNG protected samples, no creative acceptance','sourceFiles':files,'updatedFiles':new_manifest['files'],'runtimeSha256':new_manifest['runtimeSha256'],'protection':report,'checks':['protected title change refuses delivery','legal title edit preserves product/background region','all source files unchanged','native source digest bound','protection before/after PNG and report bound to manifest','skill directory has no bytecode']}
    with Path(os.environ['CRAFT_PROTECTED_EVIDENCE_FILE']).open('x') as output:json.dump(evidence,output,ensure_ascii=False,indent=2);output.write('\n')

if __name__=='__main__':unittest.main()
