#!/usr/bin/env python3
"""真实维护版回复之后注入故障；把原生事件与确认分别留证。"""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading

if sys.argv[1:] == ['--supervision-info']:
    # 元数据查询不伪装成编辑事件；已有故障记录仅统计真实编辑与确认。
    raise SystemExit(subprocess.run([os.environ['CRAFT_SUPERVISED_BINARY'], '--supervision-info']).returncode)

child = subprocess.Popen([os.environ['CRAFT_SUPERVISED_BINARY'], *sys.argv[1:]], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
log = Path(os.environ['CRAFT_SUPERVISED_LOG'])
lock = threading.Lock()
def record(row):
    with lock, log.open('a') as handle:
        handle.write(json.dumps(row) + '\n')
def confirmations():
    try:
        for line in sys.stdin.buffer:
            record({'confirmation':line.decode()})
            child.stdin.write(line); child.stdin.flush()
    except (BrokenPipeError, OSError):
        pass
    finally:
        child.stdin.close()
threading.Thread(target=confirmations, daemon=True).start()
try:
    for line in child.stdout:
        event = json.loads(line)
        record({'nativeEvent':event})
        if event['sequence'] == int(os.environ.get('CRAFT_SUPERVISED_AT', '2')):
            fault = os.environ.get('CRAFT_SUPERVISED_FAULT')
            if fault == 'duplicate':
                line = line.rstrip()[:-1] + b',"sequence":' + str(event['sequence']).encode() + b'}\n'
            elif fault == 'nonfinite':
                event['result'] = {'value':float('inf')}; line = (json.dumps(event)+'\n').encode()
            elif fault == 'semantic':
                event['result'] = {'error':'injected semantic error'}; line = (json.dumps(event)+'\n').encode()
            elif fault == 'wrong-request':
                event['arguments'] = {'id':'layer.new.layer','params':{'name':'Different'}}; line = (json.dumps(event)+'\n').encode()
            elif fault == 'save-array':
                event['result'] = []; line = (json.dumps(event)+'\n').encode()
            elif fault == 'wrong-save-path':
                event['result']['path'] += '.wrong'; line = (json.dumps(event)+'\n').encode()
            elif fault == 'wrong-plan':
                event['result']['files'] = event['result']['files'][:-1]; line = (json.dumps(event)+'\n').encode()
            elif fault == 'extra-frame':
                line += b'{}\n'
        sys.stdout.buffer.write(line); sys.stdout.buffer.flush()
    raise SystemExit(child.wait(timeout=5))
finally:
    if child.poll() is None:
        child.terminate()
        try:
            child.wait(timeout=2)
        except subprocess.TimeoutExpired:
            child.kill(); child.wait()
