"""跨计划实例复用：真实公开命令执行、路径隔离、失败保全与所属清理。"""
import importlib.util
import io
import json
import os
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT/'skills/photocraft-use/scripts'

def load():
    spec=importlib.util.spec_from_file_location('photo_task_session_test',SCRIPTS/'task_session.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def plan(name='Layer'):
    return {'schema':'craft-command-plan/v1','operations':[{'command':'layer.new.layer','params':{'name':name}}]}

class TaskSessionTests(unittest.TestCase):
    def setup_session(self,root,protected=()):
        m=load();commands=m.load('commands');original=commands.load
        binary=root/'runtime/native';binary.parent.mkdir();binary.write_bytes(b'native')
        self.edits=[];self.starts=[];self.closed=[];self.dead=False;self.reply_failure=False;self.interrupt=False;self.pause=None;self.close_pause=None;self.drift=False;self.close_error=False
        case=self
        class Process:
            pid=12345
            def poll(self):return 0 if case.dead else None
        class Native:
            timeout=120
            def __init__(self,argv):self.process=Process();case.starts.append(argv)
            def request(self,method,params):
                if method=='tools/list':return {'tools':[{'name':name,'inputSchema':({'additionalProperties':False} if case.drift else {})} for name in commands.catalog()['nativeTools']]}
                if params['name']=='command_list':return {'content':[{'type':'text','text':json.dumps([dict(r,enabled=True) for r in commands.catalog()['commands']])}]}
                if case.interrupt:raise KeyboardInterrupt()
                if case.reply_failure:raise TimeoutError('outcome_unknown')
                if case.pause:
                    case.pause[0].set();case.pause[1].wait(5)
                case.edits.append(params)
                result={'counter':len(case.edits)}
                if params['name']=='doc_open':result={'index':0}
                if params['name']=='doc_save':
                    path=params['arguments']['path'];(root/'task'/path).write_text('saved');result={'path':path}
                return {'content':[{'type':'text','text':json.dumps(result)}]}
            def close(self):
                if case.close_error:raise RuntimeError('cleanup_failed')
                if case.close_pause:case.close_pause[0].set();case.close_pause[1].wait(5)
                case.closed.append(1);case.dead=True
        native=original('mcp_session');native.Session=Native
        bootstrap=original('bootstrap')
        self.installs=self.enterContext(patch.object(bootstrap,'install',return_value={'executable':str(binary),'binarySha256':m.sha(binary)}))
        self.enterContext(patch.object(commands,'load',side_effect=lambda name:native if name=='mcp_session' else bootstrap if name=='bootstrap' else original(name)))
        return m,m.TaskSession(root/'task',root/'runtime',commands=commands,protected_paths=protected)

    def test_two_plans_keep_process_and_state_until_task_close(self):
        with tempfile.TemporaryDirectory() as td:
            m,s=self.setup_session(Path(td).resolve())
            with s:
                a=s.execute(plan('first'),'first');b=s.execute(plan('second'),'second')
                self.assertEqual([a['steps'][0]['result']['counter'],b['steps'][0]['result']['counter']],[1,2]);self.assertEqual(len(self.starts),1);self.assertEqual(self.closed,[]);self.assertEqual(self.installs.call_count,1)
            proof=json.loads((s.work/'task-session.json').read_text());self.assertEqual(proof['sessionsStarted'],1);self.assertTrue(proof['singleProcessIdentity']);self.assertTrue(proof['ownedProcessesStopped']);self.assertEqual(self.closed,[1])

    def test_stage_save_paths_use_task_root_without_overwriting_previous_stage(self):
        save={'schema':'craft-command-plan/v1','operations':[{'tool':'doc_save','params':{'path':{'$output':'project.pcraft'}}}]}
        with tempfile.TemporaryDirectory() as td:
            m,s=self.setup_session(Path(td).resolve())
            with s:
                first=s.execute(save,'first');before=(s.work/'first/project.pcraft').read_bytes();second=s.execute(save,'second')
                self.assertEqual(first['steps'][0]['params']['path'],'first/project.pcraft');self.assertEqual(second['steps'][0]['params']['path'],'second/project.pcraft');self.assertEqual((s.work/'first/project.pcraft').read_bytes(),before);self.assertTrue((s.work/'second/project.pcraft').is_file());self.assertEqual(len(self.starts),1)

    def test_invalid_initial_plan_creates_no_task_stage_installer_or_process(self):
        with tempfile.TemporaryDirectory() as td:
            m,s=self.setup_session(Path(td).resolve())
            with s:
                with self.assertRaisesRegex(ValueError,'unknown_command'):s.execute({'schema':'craft-command-plan/v1','operations':[{'command':'invented.command','params':{}}]},'bad')
                self.assertFalse(s.work.exists());self.assertEqual(self.starts,[]);self.assertEqual(self.installs.call_count,0)

    def test_unknown_blocks_later_stage_without_restart_or_replay(self):
        with tempfile.TemporaryDirectory() as td:
            m,s=self.setup_session(Path(td).resolve())
            with s:
                s.execute(plan(),'first');self.reply_failure=True;r=s.execute(plan(),'failed');self.assertEqual(r['result'],'unknown')
                with self.assertRaisesRegex(RuntimeError,'task_session_stopped'):s.execute(plan(),'later')
                self.assertFalse((s.work/'later').exists());self.assertEqual(len(self.edits),1);self.assertEqual(len(self.starts),1);self.assertEqual(json.loads((s.work/'failed/failure.json').read_text())['result'],'unknown')

    def test_dead_process_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as td:
            m,s=self.setup_session(Path(td).resolve())
            with s:
                s.execute(plan(),'first');self.dead=True
                with self.assertRaisesRegex(RuntimeError,'task_process_exited'):s.execute(plan(),'later')
                self.assertFalse((s.work/'later').exists());self.assertEqual(len(self.starts),1)

    def test_binary_change_stops_before_later_stage(self):
        with tempfile.TemporaryDirectory() as td:
            m,s=self.setup_session(Path(td).resolve())
            with s:
                s.execute(plan(),'first');Path(s.installed['executable']).write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError,'task_identity_changed'):s.execute(plan(),'later')
                self.assertFalse((s.work/'later').exists());self.assertEqual(len(self.starts),1)

    def test_interrupt_keeps_unknown_journal_and_stops_later_edits(self):
        with tempfile.TemporaryDirectory() as td:
            m,s=self.setup_session(Path(td).resolve())
            with s:
                self.interrupt=True
                with self.assertRaises(KeyboardInterrupt):s.execute(plan(),'interrupted')
                r=json.loads((s.work/'interrupted/failure.json').read_text());self.assertEqual(r['result'],'unknown');self.assertEqual(r['steps'][-1]['state'],'unknown')
                with self.assertRaisesRegex(RuntimeError,'task_session_stopped'):s.execute(plan(),'later')
                self.assertEqual(len(self.starts),1)

    def test_external_source_requires_registration_and_is_copied_under_stage(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td).resolve();source=root/'original.pcraft';source.write_bytes(b'original');m,s=self.setup_session(root,(source,))
            with s:
                r=s.execute({'schema':'craft-command-plan/v1','operations':[{'tool':'doc_open','params':{'path':{'$ref':'source.path'}}}]},'copy',{'source':str(source)});self.assertEqual(r['steps'][0]['params']['path'],'copy/inputs/source.pcraft');self.assertEqual(r['inputs']['source']['path'],'inputs/source.pcraft');self.assertEqual((s.work/'copy/inputs/source.pcraft').read_bytes(),b'original');self.assertEqual(source.read_bytes(),b'original')

    def test_unregistered_input_refused_before_task_output(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td).resolve();m,s=self.setup_session(root);source=root/'original.pcraft';source.write_bytes(b'original')
            with s:
                with self.assertRaisesRegex(ValueError,'task_input_not_protected'):s.execute(plan(),'bad',{'source':str(source)})
                self.assertFalse(s.work.exists());self.assertEqual(self.starts,[]);self.assertEqual(source.read_bytes(),b'original')

    def test_jsonl_multiple_plans_and_close_keep_same_owner(self):
        with tempfile.TemporaryDirectory() as td:
            m,s=self.setup_session(Path(td).resolve());out=io.StringIO()
            requests=[{'name':'first','plan':plan()},{'name':'second','plan':plan()},{'action':'close'}]
            with s:self.assertEqual(m.serve(s,io.StringIO(''.join(json.dumps(v)+'\n' for v in requests)),out),0)
            self.assertEqual([v['result'] for v in map(json.loads,out.getvalue().splitlines())],['PASS','PASS','CLOSED']);self.assertEqual(len(self.starts),1);self.assertEqual(self.closed,[1])

    def test_bad_jsonl_stops_without_consuming_later_plan(self):
        with tempfile.TemporaryDirectory() as td:
            m,s=self.setup_session(Path(td).resolve());out=io.StringIO()
            with s:self.assertEqual(m.serve(s,io.StringIO('{"name":"a","name":"b"}\n'+json.dumps({'name':'later','plan':plan()})+'\n'),out),1)
            self.assertEqual(self.starts,[]);self.assertFalse(s.work.exists());self.assertEqual(len(out.getvalue().splitlines()),1)

    def test_eof_closes_once_and_cannot_reenter(self):
        with tempfile.TemporaryDirectory() as td:
            m,s=self.setup_session(Path(td).resolve())
            with s:self.assertEqual(m.serve(s,io.StringIO(json.dumps({'name':'one','plan':plan()})+'\n'),io.StringIO()),0)
            with self.assertRaisesRegex(RuntimeError,'task_session_stopped'):s.__enter__()
            s.close();self.assertEqual(self.closed,[1])

    def test_common_root_outside_stage_refused_before_install_and_output(self):
        m=load();commands=m.load('commands')
        with tempfile.TemporaryDirectory() as td:
            root=Path(td).resolve();other=root/'other';other.mkdir();output=root/'stage'
            with self.assertRaisesRegex(ValueError,'invalid_session_root'):
                commands.execute(plan(),output,session_root=other,installer=lambda *a:self.fail('installed'))
            self.assertFalse(output.exists())

    def test_invalid_unicode_first_plan_has_no_task_output(self):
        with tempfile.TemporaryDirectory() as td:
            m,s=self.setup_session(Path(td).resolve())
            with s:
                with self.assertRaisesRegex(ValueError,'invalid_json_unicode'):s.execute(plan('\ud800'),'bad')
                self.assertFalse(s.work.exists());self.assertEqual(self.starts,[])

    def test_live_task_rejects_concurrent_stage_without_stopping_owner(self):
        import threading
        with tempfile.TemporaryDirectory() as td:
            m,s=self.setup_session(Path(td).resolve());entered=threading.Event();release=threading.Event();results=[]
            self.pause=(entered,release)
            with s:
                thread=threading.Thread(target=lambda:results.append(s.execute(plan(),'first')));thread.start()
                try:
                    self.assertTrue(entered.wait(5))
                    with self.assertRaisesRegex(RuntimeError,'task_session_busy'):s.execute(plan(),'concurrent')
                    self.assertFalse((s.work/'concurrent').exists());self.assertFalse(s.stopped)
                finally:release.set();thread.join(5)
                self.assertEqual(results[0]['result'],'PASS');self.assertEqual(len(self.starts),1)

    def test_bridge_unavailable_command_is_refused_before_task_creation(self):
        m=load();commands=m.load('commands')
        desktop={r['id'] for r in commands.reply_json((SCRIPTS.parent/'references/desktop-command-snapshot.json').read_text())['commands']}
        missing=next(r['id'] for r in commands.catalog()['commands'] if r['id'] not in desktop)
        with tempfile.TemporaryDirectory() as td:
            self.enterContext(patch.object(m.platform,'system',return_value='Darwin'));self.enterContext(patch.object(m.platform,'machine',return_value='arm64'))
            root=Path(td).resolve();s=m.TaskSession(root/'task',root/'runtime',mode='bridge')
            with s:
                with self.assertRaisesRegex(ValueError,'backend_command_unavailable'):s.execute({'schema':'craft-command-plan/v1','operations':[{'command':missing,'params':{}}]},'bad')
                self.assertFalse(s.work.exists())

    def test_capability_identity_stays_bound_across_stages(self):
        with tempfile.TemporaryDirectory() as td:
            m,s=self.setup_session(Path(td).resolve())
            with s:
                first=s.execute(plan(),'first');second=s.execute(plan(),'second')
                self.assertEqual(first['capabilitySnapshot']['sessionId'],s.task_id)
                self.assertEqual(first['capabilitySnapshot'],second['capabilitySnapshot'])

    def test_changed_tools_between_stages_stop_before_next_edit(self):
        with tempfile.TemporaryDirectory() as td:
            m,s=self.setup_session(Path(td).resolve())
            with s:
                s.execute(plan(),'first');self.drift=True
                result=s.execute(plan(),'changed');self.assertEqual(result['result'],'FAIL');self.assertIn('capability_mismatch',result['error'])
                self.assertEqual(len(self.edits),1);self.assertEqual(len(self.starts),1);self.assertTrue(s.stopped)

    def test_closing_owner_prevents_concurrent_new_stage(self):
        import threading
        with tempfile.TemporaryDirectory() as td:
            m,s=self.setup_session(Path(td).resolve());entered=threading.Event();release=threading.Event();self.close_pause=(entered,release)
            with s:
                s.execute(plan(),'first');thread=threading.Thread(target=s.close);thread.start()
                try:
                    self.assertTrue(entered.wait(5))
                    with self.assertRaisesRegex(RuntimeError,'task_session_busy'):s.execute(plan(),'late')
                    self.assertFalse((s.work/'late').exists());self.assertEqual(len(self.edits),1)
                finally:release.set();thread.join(5)
            self.assertEqual(self.closed,[1])

    def test_failed_cleanup_can_retry_only_the_owned_process(self):
        with tempfile.TemporaryDirectory() as td:
            m,s=self.setup_session(Path(td).resolve())
            with s:
                s.execute(plan(),'first');self.close_error=True
                with self.assertRaisesRegex(RuntimeError,'cleanup_failed'):s.close()
                self.assertFalse(self.dead);self.close_error=False;s.close()
                self.assertTrue(self.dead);self.assertEqual(self.closed,[1]);self.assertEqual(len(self.starts),1)

@unittest.skipUnless(os.environ.get('CRAFT_NATIVE_COMMANDS')=='1','native task session is opt-in')
class NativeTaskSession(unittest.TestCase):
    def test_create_revise_close_reopen_and_save_share_one_owned_instance(self):
        import hashlib
        m=load();mode=os.environ.get('CRAFT_TASK_SESSION_MODE','headless')
        def step(command,params=None):return {'command':command,'params':params or {}}
        def tool(name,params=None):return {'tool':name,'params':params or {}}
        def stage(*operations):return {'schema':'craft-command-plan/v1','operations':list(operations)}
        with tempfile.TemporaryDirectory(prefix='photo-task-native-') as td:
            root=Path(td).resolve();s=m.TaskSession(root/'task',os.environ['CRAFT_RUNTIME_HOME'],mode)
            with s:
                created=s.execute(stage(step('file.new',{'name':'One instance','width':16,'height':16,'mode':'rgb','depth':8}),step('layer.new.layer',{'name':'Keep'}),tool('doc_save',{'path':{'$output':'project.pcraft'}})),'create');self.assertEqual(created['result'],'PASS',created)
                first=s.work/'create/project.pcraft';first_sha=hashlib.sha256(first.read_bytes()).hexdigest()
                revised=s.execute(stage(step('layer.new.layer',{'name':'Revision'}),tool('doc_save',{'path':{'$output':'project.pcraft'}})),'revise');self.assertEqual(revised['result'],'PASS',revised)
                second=s.work/'revise/project.pcraft';second_sha=hashlib.sha256(second.read_bytes()).hexdigest()
                reopened=s.execute(stage(step('file.close'),tool('doc_open',{'path':'create/project.pcraft'}),tool('doc_inspect')),'reopenOriginal');self.assertEqual(reopened['result'],'PASS',reopened)
                original_names=[r['name'] for r in reopened['steps'][-1]['result']['layers']];self.assertIn('Keep',original_names);self.assertNotIn('Revision',original_names)
                latest=s.execute(stage(step('file.close'),tool('doc_open',{'path':'revise/project.pcraft'}),tool('doc_inspect')),'reopenLatest');self.assertEqual(latest['result'],'PASS',latest)
                latest_names=[r['name'] for r in latest['steps'][-1]['result']['layers']];self.assertIn('Keep',latest_names);self.assertIn('Revision',latest_names)
                final=s.execute(stage(step('layer.new.layer',{'name':'Final'}),tool('doc_save',{'path':{'$output':'project.pcraft'}}),tool('doc_inspect')),'final');self.assertEqual(final['result'],'PASS',final)
                self.assertIn('Final',[r['name'] for r in final['steps'][-1]['result']['layers']])
                self.assertEqual(hashlib.sha256(first.read_bytes()).hexdigest(),first_sha);self.assertEqual(hashlib.sha256(second.read_bytes()).hexdigest(),second_sha)
                self.assertEqual(s.started,1);self.assertTrue(all(p==s.pids[0] for p in s.pids));self.assertEqual(created['capabilitySnapshot'],final['capabilitySnapshot'])
                if mode=='bridge':self.assertTrue(s.owner.listener_verified)
            proof=json.loads((s.work/'task-session.json').read_text());self.assertTrue(proof['ownedProcessesStopped']);self.assertTrue(all(p.poll() is not None for p in s._processes()))
            report={'status':'PASS','mode':mode,'platform':sys.platform,'sessionsStarted':s.started,'stages':len(s.plans),'singleProcessIdentity':True,'ownedProcessesStopped':True,'cliBinarySha256':s.installed['binarySha256'],'desktopBinarySha256':s.desktop.get('binarySha256'),'desktopLaunches':1 if mode=='bridge' else 0,'firstProjectSha256':first_sha,'secondProjectSha256':second_sha,'priorProjectsUnchanged':True,'sourceCode':{name:hashlib.sha256((SCRIPTS/name).read_bytes()).hexdigest() for name in ('task_session.py','commands.py','desktop_session.py','mcp_session.py')},'scope':'actual owned native five-stage create/revise/close/reopen/save; no shared mutable ownership, creative, full command or host model acceptance'}
            if os.environ.get('CRAFT_TASK_SESSION_REPORT'):Path(os.environ['CRAFT_TASK_SESSION_REPORT']).write_text(json.dumps(report,indent=2)+'\n')
