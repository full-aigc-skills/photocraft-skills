"""真实原生中断窗口；只在测试进程注入，不改变生产执行器。"""
import importlib.util
import json
from pathlib import Path
import runpy
import sys
import time
mode, marker, script, *arguments = sys.argv[1:]
original_spec = importlib.util.spec_from_file_location

def pause(native_pid=None):
    Path(marker).write_text(json.dumps({'window': mode, 'nativePid': native_pid}))
    while True: time.sleep(.02)

def injected_spec(name, location, *args, **kwargs):
    spec = original_spec(name, location, *args, **kwargs)
    if Path(location).name in ('mcp_session.py', 'progress.py'):
        original_execute = spec.loader.exec_module
        def execute(module):
            original_execute(module)
            if Path(location).name == 'mcp_session.py':
                original_session = module.Session
                class PausedSession(original_session):
                    def request(self, method, params):
                        save = method == 'tools/call' and params.get('name') == 'doc_save'
                        if save and mode == 'before_save': pause(self.process.pid)
                        reply = super().request(method, params)
                        if save and mode == 'after_reply': pause(self.process.pid)
                        return reply
                module.Session = PausedSession
            else:
                original_publish = module.Journal.publish
                def publish(self, state, phase):
                    original_publish(self, state, phase)
                    if (mode == 'after_confirmed' and phase == 'reply_validated' and state.get('lastAttempt', {}).get('tool') == 'doc_save'
                            or mode in ('publishing', 'finished') and phase == mode): pause()
                module.Journal.publish = publish
        spec.loader.exec_module = execute
    return spec
importlib.util.spec_from_file_location = injected_spec
sys.argv = [script, *arguments]
runpy.run_path(script, run_name='__main__')
