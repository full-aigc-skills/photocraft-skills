from pathlib import Path
import json
import argparse
ROOT=Path(__file__).resolve().parents[1]
START='<!-- COMPLETE_SCENARIO_COMMANDS_START -->'
END='<!-- COMPLETE_SCENARIO_COMMANDS_END -->'
def build(check=False):
 suite=json.loads((ROOT/'skill-suite.json').read_text())
 domain=suite['pluginId']
 rows=json.loads((ROOT/'skills'/f'{domain}-use'/'references/command-coverage.json').read_text())['commands']
 changed=0
 for skill in suite['skills']:
  if skill['kind'] not in ('scenario','cli'):continue
  own=[r for r in rows if r['ownerSkill']==skill['name']]
  path=ROOT/'skills'/skill['name']/'references/scenario.md'
  old=path.read_text() if path.exists() else '# 通用命令操作指南 / General command guide\n'
  if START in old:old=old[:old.index(START)].rstrip()+'\n'
  lines=[START,'','## 完整归属清单 / Complete assigned command list','',f'本技能归属 {len(own)} 条命令。下面按命令族分组；上述短表若存在，仅是示例。归属按最长前缀确定，实际任务可组合其他能力的命令。','',
   'Each command below has a parameter contract in this skill’s `command-reference.md`. Assignment uses the most specific prefix; a task can combine commands from multiple capabilities.','',
   '执行顺序：检查工程和选中对象 → `commands.py describe COMMAND_ID` → 根据参数说明构造计划 → `commands.py check PLAN.json` → `commands.py run PLAN.json --output NEW_DIRECTORY` → 保存并重开原生工程、核验目标修改和非目标内容。涉及 GUI 时按 `command-usage.md` 选择 bridge 模式。','',
   'Order: inspect project and selection, describe parameters, construct and check the plan, run it, save and reopen the native project, then verify requested and unaffected content. Follow `command-usage.md` for bridge mode.','',
   '这些是命令使用入口，不能把分类或计划校验当作实际执行成功；禁用项必须重新查询上下文，超时不得直接重放。 / Classification and preflight do not prove execution acceptance. Re-query disabled commands and reconcile timed-out operations before retry.','']
  groups={}
  for r in own:groups.setdefault(r['id'].split('.')[0],[]).append(r)
  for family,items in sorted(groups.items()):
   lines += [f'### `{family}` — {len(items)}','', '| 命令 / Command | 用途 / Label | 参数入口 / Parameters |','| --- | --- | --- |']
   for r in items:lines.append('| `'+r['id']+'` | '+r['label'].replace('|','\\|').replace('\n',' ')+' | `describe '+r['id']+'` |')
   lines.append('')
  lines += [END,'']
  wanted=old.rstrip()+'\n\n'+'\n'.join(lines)
  if check:
   if not path.exists() or path.read_text()!=wanted:raise ValueError('scenario_catalog_drift: '+str(path))
  else:path.parent.mkdir(parents=True,exist_ok=True);path.write_text(wanted)
  changed+=len(own)
 if changed!=len(rows):raise ValueError('incomplete_scenario_assignment')
 print(json.dumps({'domain':domain,'commands':changed,'check':check}))
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');build(parser.parse_args().check)
