"""测试代理：真实只读调用返回后注入故障，不增加任何编辑请求。"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import threading

fault, log, proof = sys.argv[1:4]
target = 'doc_open' if fault.startswith('open-') else 'doc_inspect'
process = subprocess.Popen(sys.argv[4:], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL, text=True, bufsize=1)
targets = set()
def forward():
    try:
        for line in sys.stdin:
            request = json.loads(line)
            with Path(log).open('a') as stream: stream.write(json.dumps(request) + '\n')
            if request.get('method') == 'tools/call' and request.get('params', {}).get('name') == target:
                targets.add(request['id'])
            process.stdin.write(line); process.stdin.flush()
    finally:
        process.stdin.close()
thread = threading.Thread(target=forward, daemon=True); thread.start()
try:
    for line in process.stdout:
        reply = json.loads(line)
        if reply.get('id') in targets:
            result = reply.get('result')
            if not isinstance(result, dict) or result.get('isError'):
                raise RuntimeError('native_readonly_call_did_not_succeed')
            Path(proof).write_text(json.dumps({'nativeReplyReceived': True, 'tool': target,
                                               'replySha256': hashlib.sha256(line.encode()).hexdigest()}))
            texts = {'open-array': '[]', 'open-index-bool': '{"index":true}',
                     'open-duplicate': '{"index":0,"index":1}',
                     'inspect-missing': '{"layers":[]}',
                     'inspect-nonfinite': '{"width":NaN,"height":64,"layers":[]}'}
            reply['result'] = ({'isError': True, 'content': [{'type': 'text', 'text': 'injected readonly failure'}]}
                               if fault.endswith('-error') else {'content': [{'type': 'text', 'text': texts[fault]}]})
            print(json.dumps(reply), flush=True)
        else:
            print(line, end='', flush=True)
finally:
    try: process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.terminate()
        try: process.wait(timeout=2)
        except subprocess.TimeoutExpired: process.kill(); process.wait()
    process.stdout.close()
