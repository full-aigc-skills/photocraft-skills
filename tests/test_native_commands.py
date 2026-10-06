"""原生命令代表场景：单技能副本、实际返回引用、保存重开与图像检查。"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = json.loads((ROOT / "skill-suite.json").read_text())["pluginId"]

@unittest.skipUnless(os.environ.get("CRAFT_NATIVE_COMMANDS") == "1", "explicit native opt-in")
class NativeCommandsTests(unittest.TestCase):
    def test_advanced_plan_saved_reopened_from_one_skill(self):
        from PIL import Image
        source = ROOT / "skills" / os.environ.get("CRAFT_NATIVE_SKILL", DOMAIN + "-cli")
        self.assertIn(source.name, [p.name for p in (ROOT / "skills").iterdir() if p.is_dir()])
        before = {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in source.rglob("*") if p.is_file()}
        with tempfile.TemporaryDirectory() as tmp:
            copied = Path(tmp) / "single-skill"
            shutil.copytree(source, copied)
            spec = importlib.util.spec_from_file_location("native_commands", copied / "scripts/commands.py")
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
            plan = json.loads((copied / "examples/commands-advanced.json").read_text())
            out = Path(tmp) / "create"
            cold = os.environ.get("CRAFT_NATIVE_COLD") == "1"
            runtime_home = Path(tmp) / "empty-runtime" if cold else None
            if cold:
                self.assertFalse(runtime_home.exists())
            made = m.execute(plan, out, runtime_home=runtime_home)
            self.assertEqual(made["result"], "PASS", made.get("error"))
            suffix = {"filmcraft":"fcproj", "effectcraft":"ecproj", "photocraft":"pcraft", "vectorcraft":"vectorcraft"}[DOMAIN]
            project = out / ("project." + suffix)
            digest = hashlib.sha256(project.read_bytes()).hexdigest()
            ref = {"$ref":"project.path"}
            reopen, inspect, render = {
                "filmcraft": ({"command":"file.open","params":{"path":ref}},
                              {"command":"sequence.inspect","params":{}},
                              {"tool":"render_frame","params":{"seconds":1,"max_side":96}}),
                "effectcraft": ({"tool":"open_project","params":{"path":ref}},
                                {"tool":"get_comp","params":{}},
                                {"tool":"render_frame","params":{"time":0.5,"max_side":96,"inline":False,"path":{"$output":"preview.png"}}}),
                "photocraft": ({"tool":"doc_open","params":{"path":ref}},
                               {"tool":"doc_inspect","params":{}},
                               {"tool":"doc_export","params":{"path":{"$output":"preview.png"},"format":"png"}}),
                "vectorcraft": ({"command":"document.open","params":{"path":ref}},
                                {"command":"symbol.list","params":{}},
                                {"command":"document.export","params":{"path":{"$output":"preview.png"},"format":"png"}}),
            }[DOMAIN]
            second = Path(tmp) / "reopen"
            opened = m.execute({"schema":"craft-command-plan/v1","operations":[reopen, inspect, render]}, second, runtime_home=runtime_home, inputs={"project":project})
            self.assertEqual(opened["result"], "PASS", opened.get("error"))
            state = opened["steps"][1]["result"]
            if DOMAIN == "filmcraft":
                self.assertEqual(state["durationFrames"], 72)
                self.assertEqual([c["speed"] for c in state["video"][0]["items"]], [0.5, 1.0])
                self.assertEqual(state["video"][0]["transitions"][0]["effect"], "cross_dissolve")
            elif DOMAIN == "effectcraft":
                layers = {l["name"]:l for l in state["layers"]}
                self.assertEqual(layers["Subject"]["blendMode"], "Multiply")
                self.assertTrue(layers["Subject"]["switches"]["three_d"])
                self.assertEqual(layers["Subject"]["trackMatte"]["kind"], "Alpha Matte")
                self.assertEqual(layers["Camera"]["type"], "Camera")
            elif DOMAIN == "photocraft":
                self.assertEqual((state["width"], state["height"]), (96,64))
                layers = {l["name"]:l for l in state["layers"]}
                self.assertEqual(layers["Subject"]["effects"]["items"][0]["kind"], "Drop Shadow")
                self.assertAlmostEqual(layers["Levels 1"]["adjustment"]["Levels"]["master"]["gamma"], 1.1, places=5)
                self.assertEqual(len(layers["Curves 1"]["adjustment"]["Curves"]["master"]), 3)
            else:
                self.assertEqual(state["symbols"][0]["name"], "Emblem")
                self.assertEqual(state["symbols"][0]["instances"], 3)
                self.assertEqual(state["symbols"][0]["size"], [20.0,20.0])
            image = next(second.glob("tool-images/*.png")) if DOMAIN == "filmcraft" else second / "preview.png"
            with Image.open(image) as pixels:
                self.assertEqual(pixels.size, (96,64))
                pixels.load()
                if DOMAIN == "filmcraft":
                    self.assertGreater(pixels.convert("RGB").getpixel((48,32))[0], 200)
            self.assertEqual(hashlib.sha256(project.read_bytes()).hexdigest(), digest)
            copied_after = {str(p.relative_to(copied)): hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in copied.rglob("*") if p.is_file()}
            self.assertEqual(before, copied_after)
            if os.environ.get("CRAFT_NATIVE_REPORT"):
                Path(os.environ["CRAFT_NATIVE_REPORT"]).write_text(json.dumps({
                    "schema":"craft-native-command-sample/v1", "domain":DOMAIN, "result":"PASS",
                    "runtimeSha256":made["runtimeSha256"], "entrySha256":hashlib.sha256((copied/"scripts/commands.py").read_bytes()).hexdigest(),
                    "catalogSha256":made["catalogSha256"], "createOperations":len(made["steps"]),
                    "reopenOperations":len(opened["steps"]), "executedCommands":sorted({s["command"] for s in made["steps"]+opened["steps"] if s.get("command")}),
                    "savedProjectSha256":digest, "checks":["isolated single-skill copy", "live command context", "actual return references", "native save and reopen", "persisted domain settings", "96x64 rendered output", "source project and skill unchanged"],
                    "guiAcceptance":"NOT_RUN", "fullPerCommandAcceptance":"NOT_RUN", "coldInstall":"PASS" if cold else "NOT_RUN",
                    "skill":source.name, "skillSha256":hashlib.sha256(json.dumps(before, sort_keys=True).encode()).hexdigest(),
                    "archiveUrl":json.loads((copied/"scripts/runtime.lock.json").read_text())["artifacts"]["darwin-arm64"]["url"] if cold else None,
                    "installationMode":"one empty independent runtime per skill; public locked download" if cold else "existing runtime reuse"
                },indent=2)+"\n")
