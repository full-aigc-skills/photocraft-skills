"""真实 stdio 子进程的协议故障：请求已发送时结果未知且不重放。"""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = json.loads((ROOT / "skill-suite.json").read_text())["pluginId"]
SCRIPT = ROOT / "skills" / (DOMAIN + "-use") / "scripts/mcp_session.py"
SERVER = r'''
import json, sys
from pathlib import Path
fault, log = sys.argv[1:]
for line in sys.stdin:
    request = json.loads(line)
    if "id" not in request:
        if fault == "closed":
            break
        continue
    if request["method"] == "initialize":
        print(json.dumps({"jsonrpc":"2.0", "id":request["id"], "result":{}}), flush=True)
        continue
    with Path(log).open("a") as stream:
        stream.write(json.dumps(request) + "\n")
    response = {"jsonrpc":"2.0", "id":request["id"]}
    if fault == "malformed":
        print("not-json", flush=True)
    elif fault == "scalar":
        print("[]", flush=True)
    elif fault == "missing":
        print(json.dumps(response), flush=True)
    elif fault == "ambiguous":
        response.update(result={}, error={"code":-32603, "message":"conflicting"})
        print(json.dumps(response), flush=True)
    elif fault == "nonfinite":
        response["result"] = float("nan")
        print(json.dumps(response), flush=True)
    else:
        response["result"] = {"content":[{"type":"text","text":"accepted"}]}
        print(json.dumps(response), flush=True)
'''


def module():
    spec = importlib.util.spec_from_file_location("protocol_session", SCRIPT)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


class McpProtocolFaultTests(unittest.TestCase):
    def test_invalid_responses_are_unknown_after_exactly_one_request(self):
        for fault in ["malformed", "scalar", "missing", "ambiguous", "nonfinite"]:
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as temporary:
                log = Path(temporary) / "requests.jsonl"
                with module().Session([sys.executable, "-I", "-B", "-u", "-c", SERVER, fault, str(log)], timeout=3) as session:
                    with self.assertRaisesRegex(RuntimeError, "outcome_unknown"):
                        session.request("tools/call", {"name":"edit", "arguments":{}})
                requests = [json.loads(line) for line in log.read_text().splitlines()]
                self.assertEqual(len(requests), 1)
                self.assertEqual(requests[0]["method"], "tools/call")

    def test_closed_pipe_is_unknown_without_attempting_a_replacement_process(self):
        with tempfile.TemporaryDirectory() as temporary:
            log = Path(temporary) / "requests.jsonl"
            with module().Session([sys.executable, "-I", "-B", "-u", "-c", SERVER, "closed", str(log)], timeout=3) as session:
                self.assertEqual(session.process.wait(timeout=3), 0)
                with self.assertRaisesRegex(RuntimeError, "outcome_unknown"):
                    session.request("tools/call", {"name":"edit", "arguments":{}})
            self.assertFalse(log.exists())

    def test_valid_matching_response_remains_usable(self):
        with tempfile.TemporaryDirectory() as temporary:
            log = Path(temporary) / "requests.jsonl"
            with module().Session([sys.executable, "-I", "-B", "-u", "-c", SERVER, "valid", str(log)], timeout=3) as session:
                self.assertEqual(session.request("tools/call", {}), {"content":[{"type":"text","text":"accepted"}]})
