"""测试钩子：真实保存已完成后、回复确认前阻塞，用于杀死原工作进程。"""
import importlib.util
import json
from pathlib import Path
import runpy
import sys
import time
marker, script, *arguments = sys.argv[1:]
original_spec = importlib.util.spec_from_file_location

def injected_spec(name, location, *args, **kwargs):
    spec = original_spec(name, location, *args, **kwargs)
    if Path(location).name == 'mcp_session.py':
        original_execute = spec.loader.exec_module
        def execute(module):
            original_execute(module)
            original_session = module.Session
            class PausedSession(original_session):
                def request(self, method, params):
                    reply = super().request(method, params)
                    if method == 'tools/call' and params.get('name') == 'doc_save':
                        Path(marker).write_text(json.dumps({'saveReplyReceived': True, 'nativePid': self.process.pid}))
                        while True: time.sleep(.02)
                    return reply
            module.Session = PausedSession
        spec.loader.exec_module = execute
    return spec
importlib.util.spec_from_file_location = injected_spec
sys.argv = [script, *arguments]
runpy.run_path(script, run_name='__main__')
