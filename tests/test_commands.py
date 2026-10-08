"""完整命令目录、同会话引用和失败语义的回归；原生逐命令验收单独记录。"""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = json.loads((ROOT / "skill-suite.json").read_text())["pluginId"]
SCRIPT = ROOT / "skills" / (DOMAIN + "-use") / "scripts" / "commands.py"

def module():
    spec = importlib.util.spec_from_file_location("command_entry", SCRIPT)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value

class CommandsTests(unittest.TestCase):
    def test_invalid_tool_discovery_returns_unknown_receipt(self):
        m = module()
        identifier = m.catalog()["commands"][0]["id"]
        for invalid in [None, {}, {"tools":None}, {"tools":[None]}, {"tools":[{"name":None}]}]:
            class Fake:
                def __enter__(self): return self
                def __exit__(self,*args): pass
                def request(self,method,params): return invalid
            with self.subTest(reply=invalid), tempfile.TemporaryDirectory() as temporary:
                output = Path(temporary)/"output"
                receipt = m.execute({"schema":"craft-command-plan/v1","operations":[{"command":identifier,"params":{}}]},output,
                    installer=lambda *a:{"executable":"native","binarySha256":"a"*64},session_factory=lambda *a:Fake())
                self.assertEqual(receipt["result"],"unknown")
                self.assertEqual(receipt["steps"],[])
                self.assertEqual(json.loads((output/"failure.json").read_text()),receipt)

    def test_malformed_registry_after_edit_preserves_prior_step_and_stops(self):
        m = module()
        identifier = m.catalog()["commands"][0]["id"]
        edits = []
        class Fake:
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def request(self,method,params):
                if method=="tools/list":return {"tools":[{"name":name,"inputSchema":{"type":"object"}} for name in m.ROUTES[DOMAIN][:2]]}
                if params["name"]==m.ROUTES[DOMAIN][0]:
                    rows = [{**r,"enabled":True} for r in m.catalog()["commands"]] if not edits else [None]
                    return {"content":[{"type":"text","text":json.dumps(rows)}]}
                edits.append(params)
                return {"content":[{"type":"text","text":"{}"}]}
        with tempfile.TemporaryDirectory() as temporary:
            output=Path(temporary)/"output"
            receipt=m.execute({"schema":"craft-command-plan/v1","operations":[{"command":identifier,"params":{}},{"command":identifier,"params":{}}]},output,
                installer=lambda *a:{"executable":"native","binarySha256":"a"*64},session_factory=lambda *a:Fake())
            self.assertEqual(receipt["result"],"unknown")
            self.assertEqual(len(edits),1)
            self.assertEqual([step["state"] for step in receipt["steps"]],["succeeded"])

    def test_malformed_tool_replies_are_unknown_instead_of_unhandled_errors(self):
        m = module()
        for reply in [None, [], {"content":None}, {"content":[None]},
                      {"content":[{"type":"text"}]},
                      {"content":[{"type":"text","text":False}]},
                      {"isError":"false", "content":[]}]:
            with self.subTest(reply=reply), self.assertRaisesRegex(RuntimeError,"outcome_unknown"):
                m.parse_reply(reply)

    def test_every_reflected_command_has_exact_parameters_and_owner(self):
        m = module()
        original = json.loads((SCRIPT.parent.parent / "references/commands.json").read_text())["commands"]
        rows = {r["id"]: r for r in m.catalog()["commands"]}
        self.assertEqual(set(rows), {r["id"] for r in original})
        names = {r["name"] for r in json.loads((ROOT / "skill-suite.json").read_text())["skills"]}
        for old in original:
            self.assertEqual(rows[old["id"]]["params"], old["params"])
            self.assertIn(rows[old["id"]]["ownerSkill"], names)
            self.assertEqual(rows[old["id"]]["executionAcceptance"], "NOT_RUN")
            m.validate({"schema":"craft-command-plan/v1","operations":[{"command":old["id"],"params":{}}]})

    def test_later_unknown_command_fails_before_install_and_output(self):
        m = module()
        known = m.catalog()["commands"][0]["id"]
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "result"
            with self.assertRaisesRegex(ValueError, "unknown_command"):
                m.execute({"schema":"craft-command-plan/v1","operations":[
                    {"command":known,"params":{}},{"command":"invented.command","params":{}}]},
                    output, installer=lambda *a: self.fail("installed"))
            self.assertFalse(output.exists())

    def test_forward_duplicate_and_nonfinite_values_refused(self):
        m = module()
        known = m.catalog()["commands"][0]["id"]
        bad = [
            [{"command":known,"params":{"id":{"$ref":"later.id"}}}],
            [{"command":known,"params":{},"as":"same"},{"command":known,"params":{},"as":"same"}],
            [{"command":known,"params":{"value":float("nan")}}],
            [{"command":known,"params":{},"typo":True}],
        ]
        for ops in bad:
            with self.subTest(ops=ops), self.assertRaises(ValueError):
                m.validate({"schema":"craft-command-plan/v1","operations":ops})

    def test_nested_reference_keeps_native_integer_and_list_types(self):
        m = module()
        self.assertEqual(m.resolve({"id":{"$ref":"shape.ids.0"}}, {"shape":{"ids":[2**63+7]}}),
                         {"id":2**63+7})
        with self.assertRaisesRegex(ValueError,"unresolved_reference"):
            m.resolve({"$ref":"shape.missing"}, {"shape":{}})

    def test_native_tools_use_actual_advertised_argument_names(self):
        m = module()
        tool, args = m.native_call("shape.rectangle", {"width":20})
        self.assertEqual(tool, "command_run" if DOMAIN in ("filmcraft","photocraft")
                         else "execute_command" if DOMAIN == "effectcraft" else "run_command")
        self.assertEqual(args["id" if DOMAIN in ("filmcraft","photocraft") else "command"], "shape.rectangle")

    def test_embedded_expression_error_is_failure_even_without_mcp_iserror(self):
        m = module()
        reply = {"content":[{"type":"text","text":json.dumps({"error":"expression disabled"})}]}
        with self.assertRaisesRegex(RuntimeError,"semantic_error"):
            m.parse_reply(reply)
        with self.assertRaisesRegex(RuntimeError,"command_failed"):
            m.parse_reply({"isError":True,"content":[]})

    def test_timeout_stops_and_records_unknown_without_replay(self):
        m = module()
        first = m.catalog()["commands"][0]["id"]
        calls = []
        class Fake:
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def request(self, method, params):
                calls.append((method,params))
                if method == "tools/list":
                    return {"tools":[{"name":m.native_call(first,{})[0],"inputSchema":{"type":"object"}}, {"name":m.ROUTES[DOMAIN][0],"inputSchema":{"type":"object"}}]}
                if params["name"] == m.ROUTES[DOMAIN][0]:
                    return {"content":[{"type":"text","text":json.dumps([{**r,"enabled":True} for r in m.catalog()["commands"]])}]}
                raise TimeoutError("outcome_unknown")
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            receipt = m.execute({"schema":"craft-command-plan/v1","operations":[
                {"command":first,"params":{}},{"command":first,"params":{}}]}, out,
                installer=lambda *a: {"executable":"native","binarySha256":"a"*64},
                session_factory=lambda *a,**k: Fake())
            self.assertEqual(receipt["result"],"unknown")
            self.assertEqual(len([x for x in calls if x[0] == "tools/call" and x[1]["name"] != m.ROUTES[DOMAIN][0]]),1)
            self.assertFalse((out / "success.json").exists())
            self.assertTrue((out / "failure.json").exists())

    def test_missing_bridge_and_existing_output_refused_before_install(self):
        m = module()
        known = m.catalog()["commands"][0]["id"]
        plan = {"schema":"craft-command-plan/v1","operations":[{"command":known,"params":{}}]}
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,"output_exists"):
                m.execute(plan,Path(tmp),installer=lambda *a:self.fail("installed"))
            with self.assertRaises(ValueError):
                m.backend_argv("native",Path(tmp),"bridge",None,None)


    def test_native_image_and_plaintext_reply_saved_without_base64_in_receipt(self):
        import base64
        m = module()
        with tempfile.TemporaryDirectory() as tmp:
            reply = {"content":[{"type":"image","mimeType":"image/png","data":base64.b64encode(b"native-image").decode()}, {"type":"text","text":"rendered frame"}]}
            result = m.parse_reply(reply, Path(tmp), 3)
            self.assertEqual((Path(tmp)/result["content"][0]["path"]).read_bytes(), b"native-image")
            self.assertNotIn("data", result["content"][0])
            self.assertEqual(result["content"][1]["value"], "rendered frame")
        with self.assertRaisesRegex(RuntimeError, "outcome_unknown"):
            m.parse_reply({"content":[{"type":"text","text":"not JSON"}]})

    def test_output_references_cannot_overwrite_receipts_or_traverse(self):
        m = module()
        for value in ("../file", "file/../x", "/file", "", "file//x", "file/", "journal.json", "inputs/x", "tool-images/x"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                m.output_path(value)

    def test_wrapped_registry_tool_cannot_bypass_command_preflight(self):
        m = module()
        with self.assertRaisesRegex(ValueError, "use_command_operation"):
            m.validate({"schema":"craft-command-plan/v1","operations":[
                {"tool":m.ROUTES[DOMAIN][1],"params":{}}]})

    def test_disabled_command_stops_before_mutation_with_native_reason(self):
        m = module()
        identifier = m.catalog()["commands"][0]["id"]
        mutations = []
        class Fake:
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def request(self, method, params):
                if method == "tools/list":
                    return {"tools":[{"name":m.ROUTES[DOMAIN][0],"inputSchema":{"type":"object"}}, {"name":m.ROUTES[DOMAIN][1],"inputSchema":{"type":"object"}}]}
                if params["name"] == m.ROUTES[DOMAIN][0]:
                    return {"content":[{"type":"text","text":json.dumps([{**r,"enabled":False,"why":"selection required"} for r in m.catalog()["commands"]])}]}
                mutations.append(params)
                raise AssertionError("mutation must not run")
        with tempfile.TemporaryDirectory() as tmp:
            result = m.execute({"schema":"craft-command-plan/v1","operations":[{"command":identifier,"params":{}}]}, Path(tmp)/"out",
                installer=lambda *a:{"executable":"native","binarySha256":"a"*64}, session_factory=lambda *a:Fake())
            self.assertEqual(result["result"],"FAIL")
            self.assertEqual(result["steps"][0]["state"],"blocked")
            self.assertEqual(result["steps"][0]["reason"],"selection required")
            self.assertEqual(mutations,[])

    def test_unsafe_inner_json_is_unknown_in_command_and_tool_replies(self):
        m = module()
        payloads=['{"value":NaN}','{"value":Infinity}','{"value":-Infinity}', '{"value":1e999}', '{"id":"old","id":"new"}', '{"nested":{"value":1,"value":2}}']
        for text in payloads:
            for attachments in (False,True):
                with self.subTest(text=text,attachments=attachments),tempfile.TemporaryDirectory() as temporary:
                    with self.assertRaisesRegex(RuntimeError,'outcome_unknown'):
                        m.parse_reply({'content':[{'type':'text','text':text}]},Path(temporary) if attachments else None)

    def test_unsafe_edit_result_preserves_unknown_attempt_without_replay(self):
        m=module();identifier=m.catalog()['commands'][0]['id'];calls=[]
        class Fake:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def request(self,method,params):
                if method=='tools/list':return {'tools':[{'name':name,'inputSchema':{'type':'object'}} for name in m.ROUTES[DOMAIN][:2]]}
                if params['name']==m.ROUTES[DOMAIN][0]:return {'content':[{'type':'text','text':json.dumps([{**row,'enabled':True} for row in m.catalog()['commands']])}]}
                calls.append(params);return {'content':[{'type':'text','text':'{"saved":true,"value":NaN}'}]}
        with tempfile.TemporaryDirectory() as temporary:
            output=Path(temporary)/'output';plan={'schema':'craft-command-plan/v1','operations':[{'command':identifier,'params':{}},{'command':identifier,'params':{}}]}
            kwargs={'installer':lambda *a:{'executable':'native','binarySha256':'a'*64},'session_factory':lambda *a:Fake()}
            result=m.execute(plan,output,**kwargs)
            self.assertEqual(result['result'],'unknown');self.assertEqual(result['steps'][0]['state'],'unknown');self.assertEqual(len(calls),1)
            self.assertEqual(json.loads((output/'failure.json').read_text()),result);self.assertFalse((output/'success.json').exists())
            with self.assertRaisesRegex(ValueError,'output_exists'):m.execute(plan,output,**kwargs)
            self.assertEqual(len(calls),1)
