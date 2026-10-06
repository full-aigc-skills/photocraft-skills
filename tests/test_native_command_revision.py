"""完整命令入口的局部返工：实际对象引用、原生重开、非目标对象与像素检查。"""
import copy
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


def fingerprint(directory):
    return {str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in directory.rglob("*") if p.is_file()}


@unittest.skipUnless(os.environ.get("CRAFT_NATIVE_COMMANDS") == "1", "explicit native opt-in")
class NativeCommandRevisionTests(unittest.TestCase):
    def test_targeted_revision_survives_reopen_without_changing_other_objects(self):
        from PIL import Image
        source = ROOT / "skills" / os.environ.get("CRAFT_NATIVE_SKILL", DOMAIN + "-cli")
        original_skills = fingerprint(source)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            skill = root / "single-skill"
            shutil.copytree(source, skill)
            spec = importlib.util.spec_from_file_location("revision_commands", skill / "scripts/commands.py")
            commands = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(commands)
            runtime = root / "empty-runtime" if os.environ.get("CRAFT_NATIVE_COLD") == "1" else None
            plan = json.loads((skill / "examples/commands-revision-create.json").read_text())
            created = commands.execute(plan, root / "create", runtime_home=runtime)
            self.assertEqual(created["result"], "PASS", created.get("error"))
            suffix = {"filmcraft": "fcproj", "effectcraft": "ecproj", "photocraft": "pcraft", "vectorcraft": "vectorcraft"}[DOMAIN]
            project = root / "create" / ("project." + suffix)
            original_delivery = fingerprint(root / "create")
            project_ref = {"$ref": "project.path"}
            open_operation, inspect_operation, save_operation, render_operation = {
                "filmcraft": (
                    {"command": "file.open", "params": {"path": project_ref}},
                    {"command": "sequence.inspect", "params": {}},
                    {"command": "file.saveAs", "params": {"path": {"$output": "revised.fcproj"}}},
                    {"tool": "render_frame", "params": {"seconds": 1, "max_side": 96}}),
                "effectcraft": (
                    {"tool": "open_project", "params": {"path": project_ref}},
                    {"tool": "get_comp", "params": {}},
                    {"tool": "save_project", "params": {"path": {"$output": "revised.ecproj"}}},
                    {"tool": "render_frame", "params": {"time": 0.5, "max_side": 96, "inline": False, "path": {"$output": "preview.png"}}}),
                "photocraft": (
                    {"tool": "doc_open", "params": {"path": project_ref}},
                    {"tool": "doc_inspect", "params": {}},
                    {"tool": "doc_save", "params": {"path": {"$output": "revised.pcraft"}}},
                    {"tool": "doc_export", "params": {"format": "png", "path": {"$output": "preview.png"}}}),
                "vectorcraft": (
                    {"command": "document.open", "params": {"path": project_ref}},
                    {"command": "document.json", "params": {}},
                    {"command": "document.save", "params": {"path": {"$output": "revised.vectorcraft"}}},
                    {"command": "document.export", "params": {"format": "png", "path": {"$output": "preview.png"}}}),
            }[DOMAIN]

            def execute(operations, name, input_project):
                receipt = commands.execute({"schema": "craft-command-plan/v1", "operations": operations},
                                           root / name, runtime_home=runtime, inputs={"project": input_project})
                self.assertEqual(receipt["result"], "PASS", receipt.get("error"))
                return receipt

            original = execute([open_operation, inspect_operation, render_operation], "before", project)
            state_before = original["steps"][1]["result"]
            extra = []
            if DOMAIN == "filmcraft":
                target_id = state_before["video"][0]["items"][1]["clip"]
                change = {"command": "clip.speedDuration", "params": {"clips": [target_id], "speed": 200, "reverse": True, "ripple": False}}
            elif DOMAIN == "effectcraft":
                target_id = next(l["id"] for l in state_before["layers"] if l["name"] == "Subject")
                change = {"command": "prop.setExpression", "params": {"layer": target_id, "path": "transform/opacity", "expression": "75 + time * 10", "enabled": True}}
                extra = [{"tool": "get_property", "params": {"layer": target_id, "path": "transform/opacity", "time": 0.5}}]
            elif DOMAIN == "photocraft":
                target_id = next(l["id"] for l in state_before["layers"] if l["name"] == "Subject")
                change = {"command": "layer.setProps", "params": {"layer": target_id, "opacity": 0.5}}
            else:
                target_id = next(s["result"]["id"] for s, o in zip(created["steps"], plan["operations"]) if o.get("as") == "target")
                change = {"command": "paint.setFill", "params": {"ids": [target_id], "color": "#ff0000"}}
            revision_plan = json.loads((skill / "examples/commands-revision.json").read_text())
            revised = execute(revision_plan["operations"], "revision", project)
            revised_project = root / "revision" / ("revised." + suffix)
            reopened = execute([open_operation, inspect_operation, render_operation] + extra, "after", revised_project)
            state_after = reopened["steps"][1]["result"]
            if DOMAIN == "filmcraft":
                self.assertEqual(state_after["durationFrames"], 60)
                self.assertEqual(state_after["video"][0]["items"][1]["speed"], 2.0)
                self.assertEqual(state_after["video"][0]["items"][1]["durationFrames"], 12)
                self.assertEqual(state_before["video"][0]["items"][0], state_after["video"][0]["items"][0])
                self.assertEqual(state_before["video"][0]["transitions"], state_after["video"][0]["transitions"])
                self.assertEqual(state_before["audio"], state_after["audio"])
                self.assertEqual(state_before["settings"], state_after["settings"])
            elif DOMAIN == "effectcraft":
                self.assertEqual(state_before, state_after)
                opacity = reopened["steps"][3]["result"]
                self.assertEqual(opacity["expression"], "75 + time * 10")
                self.assertEqual(opacity["evaluated"], 80.0)
                self.assertEqual(opacity["keys"], [])
            elif DOMAIN == "photocraft":
                layers_before = {l["id"]: l for l in state_before["layers"]}
                layers_after = {l["id"]: l for l in state_after["layers"]}
                self.assertEqual(layers_after[target_id]["opacity"], 0.5)
                expected = copy.deepcopy(layers_before)
                expected[target_id]["opacity"] = 0.5
                self.assertEqual(expected, layers_after)
                self.assertEqual(state_before["channels"], state_after["channels"])
            else:
                nodes_before = {n["id"]: n for n in state_before["layers"][0]["kind"]["children"]}
                nodes_after = {n["id"]: n for n in state_after["layers"][0]["kind"]["children"]}
                self.assertEqual(set(nodes_before), set(nodes_after))
                for identity, node in nodes_before.items():
                    if identity != target_id:
                        self.assertEqual(node, nodes_after[identity])
                self.assertEqual(nodes_before[target_id]["kind"], nodes_after[target_id]["kind"])
                self.assertEqual(state_before["symbols"], state_after["symbols"])
                self.assertEqual(state_before["artboards"], state_after["artboards"])
                fill = next(i for i in nodes_after[target_id]["appearance"]["items"] if i["kind"] == "fill")
                self.assertEqual(fill["paint"]["color"], {"model": "rgb", "r": 1.0, "g": 0.0, "b": 0.0})
            image_path = lambda name: next((root / name / "tool-images").glob("*.png")) if DOMAIN == "filmcraft" else root / name / "preview.png"
            with Image.open(image_path("before")) as left, Image.open(image_path("after")) as right:
                self.assertEqual(left.size, (96, 64))
                self.assertEqual(left.size, right.size)
                a, b = left.convert("RGBA"), right.convert("RGBA")
                if DOMAIN == "filmcraft":
                    self.assertEqual(a.tobytes(), b.tobytes())
                else:
                    target_pixel = (46, 50) if DOMAIN == "vectorcraft" else (32, 32)
                    unchanged_pixel = (86, 50) if DOMAIN == "vectorcraft" else (80, 50)
                    self.assertNotEqual(a.getpixel(target_pixel), b.getpixel(target_pixel))
                    self.assertEqual(a.getpixel(unchanged_pixel), b.getpixel(unchanged_pixel))
            self.assertEqual(original_delivery, fingerprint(root / "create"))
            self.assertEqual(original_skills, fingerprint(skill))
            self.assertEqual(original_skills, fingerprint(source))
            if os.environ.get("CRAFT_NATIVE_REVISION_REPORT"):
                Path(os.environ["CRAFT_NATIVE_REVISION_REPORT"]).write_text(json.dumps({
                    "schema": "craft-native-command-revision/v1", "domain": DOMAIN, "result": "PASS",
                    "entrySha256": hashlib.sha256((skill / "scripts/commands.py").read_bytes()).hexdigest(),
                    "catalogSha256": created["catalogSha256"], "runtimeSha256": created["runtimeSha256"],
                    "testSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    "exampleSha256": {name: hashlib.sha256((skill / "examples" / name).read_bytes()).hexdigest() for name in ["commands-revision-create.json", "commands-revision.json"]},
                    "revisionCommand": change["command"], "targetIdSource": "actual native results",
                    "projectSha256": hashlib.sha256(project.read_bytes()).hexdigest(),
                    "revisedProjectSha256": hashlib.sha256(revised_project.read_bytes()).hexdigest(),
                    "operations": sum(len(r["steps"]) for r in [created, original, revised, reopened]),
                    "checks": ["single skill copy", "actual target identity", "save and reopen revision", "non-target objects preserved", "native persisted target settings", "rendered output and non-target pixel preservation", "original delivery and skills unchanged"],
                    "coldInstall": "PASS" if runtime else "NOT_RUN", "guiAcceptance": "NOT_RUN", "fullPerCommandAcceptance": "NOT_RUN"
                }, indent=2) + "\n")
