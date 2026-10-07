#!/usr/bin/env python3
"""从固定反射、原生目录快照与技能路由生成完整命令说明；不把目录观察当作执行验收。"""
import argparse
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = json.loads((ROOT / "skill-suite.json").read_text())["pluginId"]
BASE = ROOT / "skills" / (DOMAIN + "-use")

def capture():
    def load(name):
        spec = importlib.util.spec_from_file_location("capture_" + name, BASE / "scripts" / (name + ".py"))
        value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value); return value
    lock = json.loads((BASE / "scripts/runtime.lock.json").read_text())
    installed = load("bootstrap").install(lock, Path.home() / ".local/share/craft-runtimes")
    argv = [installed["executable"], "mcp"] + (["--headless"] if DOMAIN == "vectorcraft" else [])
    if DOMAIN == "effectcraft":
        argv = [installed["executable"], "--empty", "mcp"]
    with load("mcp_session").Session(argv) as session:
        tools = session.request("tools/list", {})["tools"]
        name = "command_list" if DOMAIN in ("filmcraft", "photocraft") else "list_commands"
        reply = session.request("tools/call", {"name": name, "arguments": {}})
        if reply.get("isError"):
            raise ValueError("registry_query_failed")
        data = json.loads(next(c["text"] for c in reply["content"] if c["type"] == "text"))
        rows = data["commands"] if isinstance(data, dict) else data
    snapshot = {"schema":"craft-native-command-snapshot/v1", "pluginId":DOMAIN,
                "runtimeSha256":installed["binarySha256"], "mode":"headless-empty",
                "scope":"registered commands and empty-session state only; no command execution acceptance",
                "tools":tools, "commands":rows}
    (BASE / "references/native-command-snapshot.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n")

def build(check=False):
    suite = json.loads((ROOT / "skill-suite.json").read_text())
    reflection = json.loads((BASE / "references/commands.json").read_text())
    snapshot = json.loads((BASE / "references/native-command-snapshot.json").read_text())
    current = {r["id"]:r for r in snapshot["commands"]}
    reflected = {r["id"] for r in reflection["commands"]}
    if reflected != set(current):
        raise ValueError("native_registry_inventory_drift: missing=" +
                         ",".join(sorted(set(current) - reflected)) + "; stale=" +
                         ",".join(sorted(reflected - set(current))))
    node = ast.parse((BASE / "scripts/workflow.py").read_text())
    mapped = set()
    for entry in node.body:
        if isinstance(entry, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "ALLOWED" for t in entry.targets):
            mapped = ast.literal_eval(entry.value)
    recipes = {}
    for filename in ('adjustment-mask-create.json', 'adjustment-mask-revise.json'):
        plan = json.loads((BASE / 'examples' / filename).read_text())
        for operation in plan['operations']:
            identifier = operation['params']['command'] if operation['command'] == 'native.command' else operation['command']
            recipes.setdefault(identifier, set()).add('examples/' + filename)
    rows = []
    for original in reflection["commands"]:
        identifier = original["id"]
        candidates = [(len(prefix), skill["name"]) for skill in suite["skills"]
                      if skill.get("kind") == "scenario" for prefix in skill.get("commandPrefixes", [])
                      if identifier.startswith(prefix)]
        owner = max(candidates)[1] if candidates else DOMAIN + "-cli"
        native = current.get(identifier)
        if native is None:
            raise ValueError("native_registry_drift: " + identifier)
        rows.append({**original, "ownerSkill":owner,
                     "ownerInstall":"npx skills add full-aigc-skills/" + DOMAIN + "-skills --skill " + owner,
                     "nativeUsage":"commands.py describe " + identifier + "; commands.py run PLAN.json --output NEW_DIRECTORY",
                     "workflowMapped":identifier in mapped, "usageRecipes":sorted(recipes.get(identifier, [])),
                     "observedEmptySession":native,
                     "executionAcceptance":"NOT_RUN",
                     "acceptanceScope":"full per-command contexts and outputs in this coverage audit"})
    coverage = {"schema":"craft-command-coverage/v1", "pluginId":DOMAIN,
                "runtimeSha256":snapshot["runtimeSha256"], "upstreamCommit":reflection.get("upstreamCommit"),
                "scope":"complete documentation and native-session route; not complete native acceptance",
                "workflowOperationCount":len(mapped), "workflowNativeCommandCount":sum(r["workflowMapped"] for r in rows),
                "nativeTools":[t["name"] for t in snapshot["tools"]], "commands":rows}
    outputs = {"command-coverage.json":json.dumps(coverage, ensure_ascii=False, indent=2) + "\n"}
    parts = ["# 完整原生命令参考 / Complete native command reference", "",
             "本参考逐项保留锁定参数原文与技能路由。命令执行必须满足当前工程、选择对象、素材或 GUI 前置状态。",
             "This reference preserves each pinned parameter contract and skill owner. Query live state before invocation.",
             "", "使用方法见 [完整调用指南](command-usage.md)。全部参数均为原生语法说明，不把它们假装成 JSON Schema。",
             "每项 NOT_RUN 指本轮完整逐命令验收；既有代表任务证据仍单独保留。", ""]
    for row in rows:
        native = row["observedEmptySession"]
        parts += ["## " + row["id"], "", row["label"], "",
                  "- 技能 / Owner: `" + row["ownerSkill"] + "`。",
                  "- 安装 / Install: `" + row["ownerInstall"] + "`。",
                  "- 当前工作流映射 / Workflow mapped: " + str(row["workflowMapped"]).lower() + "。",
                  "- 空会话观察 / Empty-session observation: " + str(native.get("enabled")).lower()
                  + "；禁用原因 / reason: " + str(native.get("why", "目录未提供具体原因；执行时重新查询 / query live state")) + "。",
                  "- 调用 / Invocation: `python3 -I -B \"$SKILL_DIR/scripts/commands.py\" describe " + row["id"] + "`；按原生参数构造计划后执行 run。",
                  "- 完整逐命令验收 / Full command acceptance: NOT_RUN。", "",
                  "原生参数原文 / Verbatim native parameters:", "", "```text", row["params"] or "{} (no parameter documentation in snapshot)", "```", ""]
        if row['usageRecipes']:
            parts += ['场景 / Recipes: ' + ', '.join('[' + p + '](../' + p + ')' for p in row['usageRecipes']) + '；前置条件见 [调整蒙版](adjustment-mask.md)。', '']
    outputs["command-reference.md"] = "\n".join(parts)
    for name, content in outputs.items():
        path = BASE / "references" / name
        if check:
            if not path.is_file() or path.read_text() != content:
                raise ValueError("command_documentation_drift: " + name)
        else:
            path.write_text(content)
    print(json.dumps({"pluginId":DOMAIN,"commands":len(rows),"mapped":sum(r["workflowMapped"] for r in rows),
                      "allRouted":True, "nativeExecutionAcceptance":"NOT_RUN"}))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-native", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.capture_native:
        if args.check:
            parser.error("--check is read-only")
        capture()
    build(args.check)
