"""维护版 run／batch 的逐回复监督器；确认前停止，不重放已发送命令。

候选内部接口：仅匹配显式 supervised-run 协议的维护运行时。
公开 cli.py 仍绑定原发行，待候选及固定安装验收后切换。
"""
import importlib.util
import json
import os
from pathlib import Path
import select
import subprocess
import time

ROOT = Path(__file__).resolve().parent
SCHEMA = 'photocraft-supervised-run/v1'
# 固定 f114f621 crates/codecs/src/format.rs 的可读扩展；AVIF 仅写，不能选入。
BATCH_CODEC_EXTENSIONS = frozenset('png apng jpg jpeg jpe jfif tif tiff webp gif bmp dib tga icb vda vst ico pnm pbm pgm ppm pam pfm qoi exr hdr'.split())


def load(name):
    spec = importlib.util.spec_from_file_location('supervised_run_' + name, ROOT / (name + '.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def expected_events(argv):
    """由预检后的原生 argv 生成身份序列，不启动进程或写输出。"""
    contract = load('cli_contract')
    if not argv or argv[0] != 'run':
        raise ValueError('unsupported_supervised_subcommand: $argv')
    contract.preflight(argv)
    positional, flags, last = contract.parse_argv(argv)
    events = []
    if '--new' in last:
        value, path = last['--new']
        events.append(('doc_new', contract.json_value(value, path), False))
    else:
        events.append(('doc_open', {'path': positional[0][0]}, False))
    commands = []
    for key, value, path in flags:
        if key == '--cmd':
            commands.append({'id':value, 'params':{}})
        elif key == '--params':
            commands[-1]['params'] = contract.json_value(value, path)
    events.extend(('command_run', command, True) for command in commands)
    if '--out' in last:
        arguments = {'path':last['--out'][0]}
        if '--format' in last:
            arguments['format'] = last['--format'][0]
        if '--quality' in last:
            arguments['quality'] = int(last['--quality'][0])
        events.append(('doc_save', arguments, False))
    return events


def batch_plan(argv):
    """绑定固定目录规则、动作与结果清单；任何输出目录写入之前调用。"""
    contract = load('cli_contract'); contract.preflight(argv)
    _, _, last = contract.parse_argv(argv)
    action_path, location = last['--actions']
    value = contract.json_value(Path(action_path).read_text(), location)
    if isinstance(value, dict) and 'actions' in value:
        value = value['actions']; location += '.actions'
    # 再次读取的内容也需预检；原生随后必须返回完全一致的规范化动作。
    contract.actions(value, location, batch=True)
    actions = [{'id':row['command'] if 'command' in row else row['id'], 'params':row.get('params',{})} for row in value]
    input_dir, output_dir = last['--in'][0], last['--out'][0]
    paths = []
    with os.scandir(input_dir) as entries:
        for entry in entries:
            extension = os.path.splitext(entry.name)[1][1:].lower()
            recognized = (extension in {'pcraft','psd','psb'} or extension.rsplit('\\',1)[-1] in BATCH_CODEC_EXTENSIONS)
            try:
                regular = entry.is_file()
            except OSError:
                regular = False
            if regular and recognized:
                paths.append(entry.path)
    paths.sort()
    files = []
    for path in paths:
        stem, suffix = os.path.splitext(os.path.basename(path))
        extension = last['--format'][0] if '--format' in last else suffix[1:]
        files.append({'input':path, 'target':os.path.join(output_dir,stem+'.'+extension)})
    config = {'actions':action_path, 'in':input_dir, 'out':output_dir}
    if '--format' in last:
        config['format'] = last['--format'][0]
    if '--quality' in last:
        config['quality'] = int(last['--quality'][0])
    events = [('batch_plan',config,False)]; lines = {}
    for row in files:
        events.append(('doc_open',{'path':row['input']},False))
        events.extend(('command_run',action,False) for action in actions)
        extension = last['--format'][0] if '--format' in last else os.path.splitext(row['input'])[1][1:]
        arguments = {'path':row['target'],'format':extension}
        if '--quality' in last:
            arguments['quality'] = int(last['--quality'][0])
        events.append(('doc_save',arguments,False))
        lines[len(events)] = 'ok    '+row['input']+' -> '+row['target']+'\n'
    events.append(('batch_complete',{},False))
    lines[len(events)] = str(len(files))+' succeeded, 0 failed\n'
    checks = {1:{'files':files,'steps':actions},len(events):{'succeeded':len(files),'failed':0}}
    return events, checks, lines


def execute(executable, argv, output, timeout=600, stderr=None):
    """运行固定候选并逐项校验；异常附带已核验回执和最后请求，绝不重试。

    executable 必须由调用方完成锁校验；output 接收原公开 JSON 命令行。
    """
    expected, checks, lines = batch_plan(argv) if argv and argv[0] == 'batch' else (expected_events(argv), {}, {})
    errors = load('operation_errors'); commands = load('commands')
    receipts = []; last_attempt = None
    process = subprocess.Popen([str(executable), argv[0], '--supervised', *argv[1:]],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr)
    deadline = time.monotonic() + timeout
    buffer = b''
    def unknown(reason):
        return errors.error('outcome_unknown: ' + reason + '; request not retried')
    def line():
        nonlocal buffer
        while True:
            if b'\n' in buffer:
                value, buffer = buffer.split(b'\n', 1)
                return value
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([process.stdout], [], [], remaining)[0]:
                raise unknown('supervised_reply_timeout')
            chunk = os.read(process.stdout.fileno(), 65536)
            if not chunk:
                raise unknown('supervised_reply_disconnected')
            buffer += chunk
            if len(buffer) > 64 * 1024 * 1024:
                raise unknown('supervised_reply_too_large')
    try:
        for sequence, (tool, arguments, visible) in enumerate(expected, 1):
            last_attempt = {'tool':tool, 'arguments':arguments, 'sequence':sequence, 'phase':'submitted'}
            try:
                event = load('strict_json').loads(line())
            except (ValueError, UnicodeError) as error:
                raise unknown('invalid_supervised_json') from error
            # 原生此时正在等待确认，不可能合法发送下一帧；不能先确认再发现额外回复。
            if buffer:
                raise unknown('unsolicited_supervised_frame')
            fields = {'schema', 'sequence', 'tool', 'arguments', 'visible'}
            if (not isinstance(event, dict) or set(event) not in (fields | {'result'}, fields | {'error'})
                    or event['schema'] != SCHEMA or type(event['sequence']) is not int or event['sequence'] != sequence
                    or event['tool'] != tool or type(event['visible']) is not bool or event['visible'] != visible
                    or json.dumps(event['arguments'], sort_keys=True) != json.dumps(arguments, sort_keys=True)):
                raise unknown('invalid_supervised_identity')
            if 'error' in event:
                if not isinstance(event['error'], str) or not event['error']:
                    raise unknown('invalid_supervised_error')
                raise errors.error('command_failed: ' + event['error'])
            # 复用普通工作流语义，原生合法标量／列表等 JSON 输出不擅自收窄。
            result = commands.parse_reply({'content':[{'type':'text', 'text':json.dumps(event['result'], allow_nan=False)}]})
            result = commands.validate_tool_reply(tool, result, arguments)
            if tool == 'doc_save' and result['path'] != arguments['path']:
                raise unknown('supervised_save_path_mismatch')
            if sequence in checks and json.dumps(result,sort_keys=True) != json.dumps(checks[sequence],sort_keys=True):
                raise unknown('invalid_supervised_batch_result')
            last_attempt['phase'] = 'reply_validated'
            receipts.append({'tool':tool, 'arguments':arguments, 'result':result, 'sequence':sequence})
            if visible:
                output.write(json.dumps({'command':arguments['id'], 'result':result}, ensure_ascii=False) + '\n')
                output.flush()
            if sequence in lines:
                output.write(lines[sequence]); output.flush()
            try:
                process.stdin.write(('continue ' + str(sequence) + '\n').encode())
                process.stdin.flush()
            except OSError as error:
                raise unknown('supervised_confirmation_disconnected') from error
        process.stdin.close()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise unknown('supervised_exit_timeout')
        try:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([process.stdout], [], [], remaining)[0]:
                raise unknown('supervised_exit_timeout')
            remainder = os.read(process.stdout.fileno(), 1)
            if remainder or buffer:
                raise unknown('unexpected_supervised_reply')
            code = process.wait(timeout=max(0.001, deadline-time.monotonic()))
        except subprocess.TimeoutExpired as error:
            raise unknown('supervised_exit_timeout') from error
        if code != 0:
            raise unknown('supervised_exit_nonzero')
        return {'result':'PASS', 'receipts':receipts, 'lastAttempt':last_attempt, 'replay':False}
    except BaseException as error:
        error.receipts = receipts
        error.lastAttempt = last_attempt
        raise
    finally:
        if not process.stdin.closed:
            try:
                process.stdin.close()
            except OSError:
                pass
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait()
        process.stdout.close()
