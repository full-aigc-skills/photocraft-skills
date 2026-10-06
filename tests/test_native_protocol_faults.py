"""公开原生 CLI 保存成功后丢失可信回复：保留文件、未知回执且不重放。"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = json.loads((ROOT / "skill-suite.json").read_text())["pluginId"]
PROXY = r'''
import json, subprocess, sys, threading
from pathlib import Path
fault, save_tool, save_key, save_id, log = sys.argv[1:6]
process = subprocess.Popen(sys.argv[6:], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
save_request = {"id":None}
def forward():
    try:
        for line in sys.stdin:
            request = json.loads(line)
            params = request.get("params", {})
            if request.get("method") == "tools/call" and params.get("name") == save_tool and (not save_key or params.get("arguments", {}).get(save_key) == save_id):
                save_request["id"] = request["id"]
            process.stdin.write(line)
            process.stdin.flush()
    finally:
        process.stdin.close()
thread = threading.Thread(target=forward, daemon=True)
thread.start()
try:
    for line in process.stdout:
        reply = json.loads(line)
        if save_request["id"] is not None and reply.get("id") == save_request["id"]:
            result = reply.get("result")
            if not isinstance(result, dict) or result.get("isError"):
                raise RuntimeError("native save did not succeed before fault")
            with Path(log).open("a") as stream:
                stream.write(json.dumps({"id":reply["id"], "nativeSaveSucceeded":True}) + "\n")
            if fault == "malformed":
                print("not-json", flush=True)
            elif fault == "scalar":
                print("[]", flush=True)
            elif fault == "missing":
                print(json.dumps({"id":reply["id"]}), flush=True)
            elif fault == "ambiguous":
                reply["error"] = {"code":-32603, "message":"conflicting"}
                print(json.dumps(reply), flush=True)
            elif fault == "nonfinite":
                reply["result"] = float("nan")
                print(json.dumps(reply), flush=True)
            elif fault.startswith("inner-"):
                text = {"inner-nonfinite": '{"saved":true,"value":NaN}', "inner-overflow": '{"saved":true,"value":1e999}', "inner-duplicate": '{"saved":true,"saved":false}'}[fault]
                reply["result"] = {"content":[{"type":"text","text":text}]}
                print(json.dumps(reply), flush=True)
            else:
                reply["result"] = {"content":[None]}
                print(json.dumps(reply), flush=True)
        else:
            print(line, end="", flush=True)
finally:
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
    process.stdout.close()
'''


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fingerprint(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file()}


@unittest.skipUnless(os.environ.get("CRAFT_NATIVE_PROTOCOL_FAULTS") == "1", "explicit public native fault-injection opt-in")
class NativeProtocolFaultTests(unittest.TestCase):
    def test_native_save_happens_once_unknown_reply_preserves_reopenable_project(self):
        source = ROOT / "skills" / os.environ.get("CRAFT_NATIVE_SKILL", DOMAIN + "-cli")
        before = fingerprint(source)
        cases = []
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            skill = root / "single-skill"
            shutil.copytree(source, skill)
            commands = load(skill / "scripts/commands.py", "native_fault_commands")
            transport = load(skill / "scripts/mcp_session.py", "native_fault_session")
            plan = json.loads((skill / "examples/commands-advanced.json").read_text())
            save_tool, save_key, save_id, suffix, opening, inspection = {
                "filmcraft": ("command_run", "id", "file.saveAs", "fcproj", {"command":"file.open", "params":{"path":{"$ref":"project.path"}}}, {"command":"sequence.inspect", "params":{}}),
                "effectcraft": ("save_project", "", "", "ecproj", {"tool":"open_project", "params":{"path":{"$ref":"project.path"}}}, {"tool":"get_comp", "params":{}}),
                "photocraft": ("doc_save", "", "", "pcraft", {"tool":"doc_open", "params":{"path":{"$ref":"project.path"}}}, {"tool":"doc_inspect", "params":{}}),
                "vectorcraft": ("run_command", "command", "document.save", "vectorcraft", {"command":"document.open", "params":{"path":{"$ref":"project.path"}}}, {"command":"symbol.list", "params":{}}),
            }[DOMAIN]
            save_index = next(i for i, step in enumerate(plan["operations"])
                              if step.get("tool") == save_tool or (save_key and step.get("command") == save_id))
            plan["operations"].append(inspection)
            runtime = root / "empty-runtime"
            self.assertFalse(runtime.exists())
            for fault in ["malformed", "scalar", "missing", "ambiguous", "nonfinite", "tool-content", "inner-nonfinite", "inner-overflow", "inner-duplicate"]:
                with self.subTest(fault=fault):
                    output = root / fault
                    log = root / (fault + ".jsonl")
                    def factory(argv):
                        return transport.Session([sys.executable, "-I", "-B", "-u", "-c", PROXY,
                                                  fault, save_tool, save_key, save_id, str(log), *argv], timeout=30)
                    failed = commands.execute(plan, output, runtime_home=runtime, session_factory=factory)
                    self.assertEqual(failed["result"], "unknown", failed.get("error"))
                    self.assertIn("outcome_unknown", failed["error"])
                    self.assertEqual(len(failed["steps"]), save_index + 1)
                    self.assertEqual(failed["steps"][-1]["state"], "unknown")
                    self.assertFalse((output / "success.json").exists())
                    self.assertEqual(json.loads((output / "journal.json").read_text()), failed)
                    self.assertEqual(json.loads((output / "failure.json").read_text()), failed)
                    saves = [json.loads(line) for line in log.read_text().splitlines()]
                    self.assertEqual(len(saves), 1)
                    self.assertTrue(saves[0]["nativeSaveSucceeded"])
                    project = output / ("project." + suffix)
                    saved = fingerprint(output)
                    reopened = commands.execute({"schema":"craft-command-plan/v1", "operations":[opening, inspection]},
                                                root / (fault + "-reopened"), runtime_home=runtime, inputs={"project":project})
                    self.assertEqual(reopened["result"], "PASS", reopened.get("error"))
                    state = reopened["steps"][1]["result"]
                    if DOMAIN == "filmcraft":
                        self.assertEqual(state["durationFrames"], 72)
                    elif DOMAIN == "effectcraft":
                        self.assertEqual({layer["name"] for layer in state["layers"]}, {"Subject", "Matte", "Camera"})
                    elif DOMAIN == "photocraft":
                        self.assertEqual((state["width"], state["height"]), (96, 64))
                        self.assertEqual(len(state["layers"]), 4)
                    else:
                        self.assertEqual(state["symbols"][0]["instances"], 3)
                    self.assertEqual(saved, fingerprint(output))
                    cases.append({"fault":fault, "nativeSaveCount":len(saves), "result":failed["result"],
                                  "startedSteps":len(failed["steps"]), "reopen":"PASS",
                                  "projectSha256":hashlib.sha256(project.read_bytes()).hexdigest(),
                                  "runtimeSha256":failed["runtimeSha256"]})
            self.assertEqual(before, fingerprint(skill))
            self.assertEqual(before, fingerprint(source))
            if os.environ.get("CRAFT_NATIVE_PROTOCOL_REPORT"):
                Path(os.environ["CRAFT_NATIVE_PROTOCOL_REPORT"]).write_text(json.dumps({
                    "schema":"craft-native-protocol-fault-first-use/v1", "domain":DOMAIN, "result":"PASS",
                    "coldInstall":"PASS", "cases":cases,
                    "entrySha256":hashlib.sha256((skill / "scripts/commands.py").read_bytes()).hexdigest(),
                    "transportSha256":hashlib.sha256((skill / "scripts/mcp_session.py").read_bytes()).hexdigest(),
                    "testSha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    "checks":["single skill copy", "fresh public locked runtime", "native save before injected response fault", "one save request", "unknown journal and failure receipt", "no later operations", "saved native project reopened", "original delivery and skills unchanged"],
                    "scope":"nine injected response faults after real native save; not exhaustive commands or GUI acceptance"
                }, indent=2) + "\n")
