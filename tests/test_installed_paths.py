"""真实技能目录调用合同；覆盖用户、项目和插件布局以及空格路径。"""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]
class InstalledPathTests(unittest.TestCase):
 def test_examples_use_loaded_skill_directory(self):
  for path in (ROOT / 'skills').rglob('*.md'):
   with self.subTest(file=str(path.relative_to(ROOT))):
    content = path.read_text()
    self.assertNotIn('/mnt/skills/user/', content)
    if path.name == 'SKILL.md':
     self.assertIn('SKILL_DIR', content)
     self.assertIn('实际加载', content)
     locations = re.findall(r'(?:~/.agents/skills/|`\.agents/skills/|其 `skills/)('+re.escape(path.parent.name.split('-')[0])+r'-[a-z-]+)', content)
     self.assertEqual(set(locations), {path.parent.name}, '安装位置示例必须只引用当前技能自身')
 def test_documented_script_paths_run_in_installation_layouts(self):
  for skill in sorted((ROOT / 'skills').iterdir()):
   content = (skill / 'SKILL.md').read_text()
   scripts = set(re.findall(r'"\$SKILL_DIR/(scripts/[^"\s]+\.py)"', content))
   self.assertIn('scripts/bootstrap.py', scripts)
   # 所有例示入口的 argparse --help 无安装副作用，避免用安装成功替代任务验收。
   for layout in ('user home/.agents/skills', 'project with spaces/.agents/skills', 'plugin cache/skills'):
    with self.subTest(skill=skill.name, layout=layout), tempfile.TemporaryDirectory() as directory:
     target = Path(directory) / layout / skill.name
     shutil.copytree(skill, target, ignore=shutil.ignore_patterns('__pycache__'))
     env = dict(os.environ, SKILL_DIR=str(target))
     for script in scripts:
      result = subprocess.run(['/bin/sh', '-c', 'python3 -I -B "$SKILL_DIR/' + script + '" --help'], cwd=directory, env=env, text=True, capture_output=True, timeout=30)
      self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
     self.assertFalse(any(target.rglob('*.pyc')))
if __name__ == '__main__':
 unittest.main()
