#!/usr/bin/env python3
"""同步单技能安装资源；知识入口与场景指南分别维护，来源仍在本独立仓库。"""
import argparse
from pathlib import Path
import json
import shutil
import sys
ROOT=Path(__file__).resolve().parents[1]
def sync(check=False):
 # 完整归属清单独立于共享参考，同步前先验证，避免发布过期的场景列表。
 import subprocess
 subprocess.run([sys.executable,'-I','-B',str(ROOT/'scripts/build_scenario_catalog.py'),'--check'],check=True)
 suite=json.loads((ROOT/'skill-suite.json').read_text());base=ROOT/'skills'/(suite['pluginId']+'-use');errors=[]
 for entry in suite['skills']:
  if entry['name']==base.name:continue
  target=ROOT/'skills'/entry['name']
  for folder in ['scripts','examples']:
   for source in sorted((base/folder).rglob('*')):
    if not source.is_file() or '__pycache__' in source.parts:continue
    destination=target/folder/source.relative_to(base/folder)
    if check:
     if not destination.is_file() or destination.read_bytes()!=source.read_bytes():errors.append(str(destination.relative_to(ROOT)))
    else:destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,destination)
  for source in sorted((base/'references').glob('*')):
   if source.name in {'commands.json','scenario.md'} or not source.is_file():continue
   destination=target/'references'/source.name
   data=source.read_bytes() if source.suffix == '.json' else source.read_text().replace(base.name,target.name).encode()
   if check:
    if not destination.is_file() or destination.read_bytes()!=data:errors.append(str(destination.relative_to(ROOT)))
   else:destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(data)
 if errors:raise ValueError('skill_resource_drift: '+', '.join(errors))
if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args()
 sync(args.check);print('skill suite resources verified' if args.check else 'skill suite resources synchronized')
