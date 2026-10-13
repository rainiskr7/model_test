#!/usr/bin/env python3
"""C1-C6 test driver. Only owns fixture processes and writes beneath .codex_work.
Shell entry points select a suite and accept the runner path as their argument.
No third party imports; no API requests. INCONCLUSIVE is never counted as PASS.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess as sp
import sys
import tempfile
import time

BASH = '/bin/bash'
WORKSPACE = Path(__file__).resolve().parents[4]
if not (WORKSPACE / 'foundation_model_test_non_thinking').is_dir():
    raise SystemExit('test helper must live in shared/harness/tests in a repository')
WORK = WORKSPACE / '.codex_work' / 'harness_stop_guard'
WORK.mkdir(parents=True, exist_ok=True)
FAILURES = 0
PASSES = 0
INCONCLUSIVE = 0
OWNED = []
ROOT = None

def check(tag, name, ok, detail=''):
    global FAILURES, PASSES
    if ok: PASSES += 1
    else: FAILURES += 1
    print(f'[{tag}] {"PASS" if ok else "FAIL"} {name}' + (f' — {detail}' if detail else ''), flush=True)
    return ok

def inconclusive(name, detail):
    global INCONCLUSIVE
    INCONCLUSIVE += 1
    print(f'[신규] INCONCLUSIVE {name} — {detail}', flush=True)

def write(path, text, executable=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    if executable: path.chmod(0o755)
    return path

def envbase():
    # No caller keys, endpoint overrides, task overrides or shell functions leak in.
    keep = {k: os.environ[k] for k in ('HOME', 'USER', 'LANG') if k in os.environ}
    keep.update(PATH=os.environ.get('PATH', '/usr/bin:/bin'), TMPDIR=str(ROOT / 'tmp'),
                LC_ALL='C', PYTHONDONTWRITEBYTECODE='1', HF_HUB_OFFLINE='1', HF_DATASETS_OFFLINE='1',
                TRANSFORMERS_OFFLINE='1', OPENAI_API_KEY='fixture-only')
    (ROOT / 'tmp').mkdir(exist_ok=True)
    return keep

def run(args, env=None, timeout=45, cwd=None):
    return sp.run(args, env=env, cwd=cwd, text=True, stdout=sp.PIPE, stderr=sp.STDOUT, timeout=timeout)

def proc_available():
    try:
        r = run(['/bin/ps', '-p', str(os.getpid()), '-o', 'pid='])
    except (PermissionError, FileNotFoundError):
        return False
    return r.returncode == 0 and str(os.getpid()) in r.stdout

def stat(pid):
    return run(['/bin/ps', '-p', str(pid), '-o', 'stat=']).stdout.strip()

def stamp(pid):
    env = dict(os.environ, LC_ALL='C')
    return run(['/bin/ps', '-p', str(pid), '-o', 'lstart='], env).stdout.strip()

def alive(pid):
    try: os.kill(pid, 0)
    except ProcessLookupError: return False
    return not stat(pid).startswith('Z')

def descendants(pid):
    result = [pid]
    children = run(['/usr/bin/pgrep', '-P', str(pid)])
    for x in children.stdout.split(): result.extend(descendants(int(x)))
    return result

def launch(args, env, logfile, reset_int=True):
    # exec preserves this owned PID, and resets inherited background SIGINT.
    if reset_int: args = ['/usr/bin/perl', '-e', '$SIG{INT}="DEFAULT"; exec @ARGV', *args]
    f = logfile.open('w')
    p = sp.Popen(args, env=env, stdin=sp.DEVNULL, stdout=f, stderr=sp.STDOUT)
    f.close(); OWNED.append(p)
    return p

def waitfor(predicate, seconds=10):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate(): return True
        time.sleep(.03)
    return False

def finish(p, timeout=17):
    try: return p.wait(timeout=timeout)
    except sp.TimeoutExpired: return None

def cleanup_process(p, known=()):
    # Every root passed here was spawned by this driver. Snapshot before killing.
    pids = list(known)
    if p.poll() is None:
        if proc_available(): pids += descendants(p.pid)
        else: pids += [p.pid]
    for pid in set(pids):
        try: os.kill(pid, signal.SIGKILL)
        except ProcessLookupError: pass
    try: p.wait(timeout=3)
    except sp.TimeoutExpired: pass

def shell_function(lib, function, *args):
    return run([BASH, '-c', 'source "$1"; shift; "$@"', 'test', str(lib), function, *map(str, args)], envbase())

def payload(task, limit=None):
    count = 100 if limit is None else min(100, int(limit) if limit >= 1 else math.ceil(100 * limit))
    return {'results': {task: {'acc,none': .5, 'acc_stderr,none': .01}},
            'n-samples': {task: {'original': 100, 'effective': count}}, 'config': {'limit': limit}}

FAKE = r'''#!/usr/bin/env python3
import json,math,os,pathlib,signal,subprocess,sys,time
args=sys.argv[1:]
task=args[args.index('--tasks')+1]; out=pathlib.Path(args[args.index('--output_path')+1])
base=pathlib.Path(os.environ['CASE']); mode=os.environ.get('FAKE_MODE','good')
with (base/'calls').open('a') as f:f.write(task+'\n')
print('fixture stdout',flush=True); print('fixture stderr',file=sys.stderr,flush=True)
if mode in ('hang','ignore'):
    if mode=='ignore':signal.signal(signal.SIGTERM,signal.SIG_IGN)
    child=subprocess.Popen(['/bin/sleep','300'])
    with (base/'pid_ledger').open('a') as f:f.write(json.dumps([os.getpid(),child.pid])+'\n')
    (base/'ready').write_text(json.dumps({'pid':os.getpid(),'child':child.pid,'tmp':str(out.parent)}))
    time.sleep(300); sys.exit(0)
if mode=='rc7':sys.exit(7)
limit=float(os.environ['FAKE_LIMIT']) if 'FAKE_LIMIT' in os.environ else None
if '--limit' in args:limit=float(args[args.index('--limit')+1])
effective=100 if limit is None else min(100,int(limit) if limit>=1 else math.ceil(100*limit))
d={'results':{task:{'acc,none':.5}},'n-samples':{task:{'original':100,'effective':effective}},'config':{'limit':limit}}
if mode=='metric':d['results'][task]={'sample_len':100}
if mode=='other':d['results']={'other_task':{'acc,none':.5}}
if mode=='mixed':d['results']['other_task']={'acc,none':.5}
if mode=='samples':d['n-samples'][task]['effective']=99
if mode=='nan':d['results'][task]['acc,none']=float('nan')
name=out.with_name(out.stem+'_2026-01-01T00-00-00.json')
name.write_text('{' if mode=='broken' else json.dumps(d))
if mode=='two':out.with_name(out.stem+'_2026-01-02T00-00-00.json').write_text(json.dumps(d))
if mode=='chmod':out.parent.parent.chmod(0o555)
'''

class Harness:
    def __init__(self, target):
        self.target = target
        self.repo = target.parents[2]
        self.thinking = 'tasks_thinking' in target.read_text()
        base_tasks = re.findall(r'^    (kmmlu_[a-z_]+)\s*$', target.read_text(), re.M)
        self.tasks = [s.replace('kmmlu_', 'kmmlu_think_', 1) for s in base_tasks] if self.thinking else base_tasks
        self.lib = target.parent / 'harness_lib.sh'
        self.bin = ROOT / 'bin'
        write(self.bin / 'lm_eval', FAKE, True)
        write(ROOT / 'adapter.json', json.dumps({'non-thinking': 'PATH=<fixture>/bin:$PATH',
              'thinking': 'LM_EVAL_BIN=<fixture>/bin/lm_eval', 'fake_sha256': hashlib.sha256(FAKE.encode()).hexdigest()}, indent=2))
    def case(self, label, mode='good', skip=True):
        case = ROOT / label; case.mkdir()
        rd = case / 'results/fixture_model/session/language/harness'; rd.mkdir(parents=True)
        if skip:
            for task in self.tasks[1:]: write(rd / (task + '_existing.json'), json.dumps(payload(task)))
        env = envbase(); env.update(MODEL_TEST_BASE=str(case), EVAL_TIMESTAMP='session', CASE=str(case),
            FAKE_MODE=mode, PATH=str(self.bin) + ':' + env['PATH'])
        if self.thinking: env['LM_EVAL_BIN'] = str(self.bin / 'lm_eval')
        return case, rd, env
    def cmd(self):
        return [BASH, str(self.target), 'fixture-model', 'fixture-tokenizer', 'http://127.0.0.1:18999/v1/chat/completions']
    def execute(self, case, env):
        if env.get('FAKE_MODE') in ('hang','ignore'):
            ledger=case/'pid_ledger'
            before=len(ledger.read_text().splitlines()) if ledger.exists() else 0
            log=case/'runner.log';p=launch(self.cmd(),env,log)
            rc=finish(p,3)
            if rc is None:
                lines=ledger.read_text().splitlines()[before:] if ledger.exists() else []
                children=[pid for line in lines for pid in json.loads(line)]
                cleanup_process(p,children)
                return sp.CompletedProcess(self.cmd(),124,log.read_text()+'\nfixture contender timeout\n')
            return sp.CompletedProcess(self.cmd(),rc,log.read_text())
        r = run(self.cmd(), env, timeout=90); write(case / 'runner.log', r.stdout); return r
    def one_result(self, rd):
        return list(rd.glob(self.tasks[0] + '_*.json'))

def harness_suite(target):
    h = Harness(target)
    check('보존', 'C4 task list has 45 subjects', len(h.tasks) == 45)
    case, rd, env = h.case('normal45', skip=False)
    r = h.execute(case, env)
    check('보존', 'C4 45 valid subjects rc0 / 45 outputs', r.returncode == 0 and len(list(rd.glob('*.json'))) == 45, f'rc={r.returncode}')
    (case / 'calls').unlink(missing_ok=True)
    r = h.execute(case, env)
    check('보존', 'C4 second run 45 skips / zero invocations', r.returncode == 0 and r.stdout.count('[skip]') == 45 and not (case/'calls').exists())
    case, rd, env = h.case('rc7', 'rc7'); r = h.execute(case, env)
    check('보존', 'C1 rc7 stdout/stderr and task failure', r.returncode == 1 and 'fixture stdout' in r.stdout and 'fixture stderr' in r.stdout and '[WARN]' in r.stdout)
    for mode, reason in [('broken','json_parse'),('metric','missing_metric'),('other','missing_task'),('mixed','unrelated_task'),('samples','sample_count'),('nan','nonfinite_metric'),('two','output_count:2')]:
        case, rd, env = h.case('invalid_'+mode, mode); r = h.execute(case, env)
        saved = list(rd.glob('.failed_*/*.json'))
        check('재현', 'C2 '+mode+' rejected / preserved / reason', r.returncode == 1 and not h.one_result(rd) and bool(saved) and reason in r.stdout, f'rc={r.returncode}')
    # C3 deliberately uses filesystem permissions, not a stubbed mv.
    case, rd, env = h.case('move_failure','chmod'); r = h.execute(case, env)
    check('재현', 'C3 real mv failure / rc1 / temp preserved', r.returncode == 1 and 'move_failed' in r.stdout and ('Permission denied' in r.stdout or 'Operation not permitted' in r.stdout) and bool(list(rd.glob('.tmp_*/*.json'))), f'rc={r.returncode}')
    rd.chmod(0o755); env['FAKE_MODE']='good'; r=h.execute(case, env)
    check('신규', 'C3 retry retains failed output and remeasures', r.returncode == 0 and bool(list(rd.glob('.failed_*/*.json'))) and len(h.one_result(rd)) == 1)
    for limit in (2, 2.5, .1):
        case, rd, env = h.case('limit_'+str(limit)); env.update(FAKE_LIMIT=str(limit), LIMIT=str(limit)); r=h.execute(case,env)
        if h.thinking:
            check('신규', f'C2 LIMIT={limit} accepted', r.returncode == 0 and bool(h.one_result(rd)), f'rc={r.returncode}')
        else:
            # non-thinking 러너는 --limit 을 넘기지 않는다 → 환경 LIMIT 은 무시되고 limit 결과는 거부돼야 한다.
            check('신규', f'C2 LIMIT={limit} env ignored, limit output rejected (non-thinking)', r.returncode == 1 and not h.one_result(rd) and 'run_limit_mismatch' in r.stdout, f'rc={r.returncode}')
    for label, configured in [('absent',None), ('different','3')]:
        case,rd,env=h.case('limit_'+label);env['FAKE_LIMIT']='2'
        if configured: env['LIMIT']=configured
        # Thinking fake receives --limit: use structural fixture function below to
        # cover mismatched values without changing runner arguments.
        if configured and h.thinking: continue
        r=h.execute(case,env)
        check('신규','C2 LIMIT '+label+' rejects limit2 output',r.returncode==1 and not h.one_result(rd) and 'run_limit_mismatch' in r.stdout)
    if h.lib.exists():
        fixture=write(ROOT/'limit_fixture.json',json.dumps(payload(h.tasks[0],2)))
        check('신규','C2 run-limit explicit mismatch rejected', shell_function(h.lib,'harness_validate_run_limit',fixture,'3').returncode==1)
        # Both real fixture kinds are checked by the standard-library validator.
        for repo_name in ('foundation_model_test_non_thinking','foundation_model_test_thinking'):
            files=sorted((WORKSPACE/repo_name/'results').glob('*/*/language/harness/*.json'))
            # results/ 가 없는 호스트(예: 리눅스 서버로 시험 파일만 보낸 경우)는 데이터 부재 — 결함이 아니다.
            if not files:
                if (WORKSPACE/repo_name/'results').is_dir(): check('보존','C2 real fixture '+repo_name,False,'no fixture')
                else: inconclusive('C2 real fixture '+repo_name,'no results/ on this host')
                continue
            p=files[0]; data=json.loads(p.read_text()); task=next(iter(data['results']))
            r=shell_function(h.lib,'harness_validate_structure',p,task)
            check('보존','C2 real fixture '+repo_name,r.returncode==0,r.stdout.strip())
        inventory=[]; rejected=[]
        for p in sorted((h.repo/'results').glob('*/*/language/harness/*.json')):
            raw=p.read_bytes(); d=json.loads(raw); task=re.split(r'_20\d\d-',p.stem)[0]
            r=shell_function(h.lib,'harness_validate_structure',p,task)
            inventory.append({'path':str(p),'sha256':hashlib.sha256(raw).hexdigest(),'rc':r.returncode,'reason':r.stdout.strip()})
            if r.returncode: rejected.append(str(p)+': '+r.stdout.strip())
        write(ROOT/'C4_inventory.json',json.dumps(inventory,indent=2))
        if (h.repo/'results').is_dir():
            check('보존','C4 existing top-level JSON inventory',bool(inventory) and not rejected,f'{len(inventory)} files, {len(rejected)} rejected')
        else:
            inconclusive('C4 existing top-level JSON inventory','no results/ on this host')
        if rejected: write(ROOT/'C4_rejected.txt','\n'.join(rejected))
    else:
        inconclusive('C2/C4 validator functions','target has no harness_lib.sh')
    # Lock open error, tool selection and errors are independent of ps permission.
    case,rd,env=h.case('lock_open'); (rd/'.harness.lock').mkdir(); r=h.execute(case,env)
    check('신규','C5 lock open failure rc4',r.returncode==4,f'rc={r.returncode}')
    fakebin=ROOT/'flock_bin'
    write(fakebin/'flock','#!/bin/bash\nprintf "%s\\n" "$*" > "$CASE/flock_args"\nexit "${FLOCK_RC:-75}"\n',True)
    for fake_rc,expected in [(75,3),(1,4)]:
        case,rd,env=h.case('flock_'+str(fake_rc));env.update(PATH=str(fakebin)+':'+env['PATH'],FLOCK_RC=str(fake_rc));r=h.execute(case,env)
        args=(case/'flock_args').read_text() if (case/'flock_args').exists() else ''
        check('신규',f'C5 flock rc{fake_rc} maps rc{expected}',r.returncode==expected and '-n -E 75 9' in args,f'rc={r.returncode}')
    if sys.platform.startswith('linux') and shutil.which('flock'):
        # 실제 flock: 잠금 도구가 flock 으로 선택되고 정상 실행된다. 이어지는 harness_lock_tests 의 경합·KILL 시험도 실제 flock 으로 돈다.
        case,rd,env=h.case('real_flock');r=h.execute(case,env)
        check('신규','C5 real flock selected and acquired (Linux)',r.returncode==0 and 'lock acquired (flock)' in r.stdout,f'rc={r.returncode}')
    else:
        inconclusive('C5 Linux flock real implementation','no real flock on this host; fake verifies selection/rc mapping only')
    harness_lock_tests(h)
    if proc_available(): harness_process_tests(h)
    else:
        inconclusive('C1 TERM/INT/grace','ps denied: real process tests not launched')

def harness_process_tests(h):
    for sig,expected in [(signal.SIGTERM,143),(signal.SIGINT,130)]:
        case,rd,env=h.case('signal_'+str(sig),'hang',skip=False); log=case/'runner.log'
        p=launch(h.cmd(),env,log); known=[]
        try:
            ready=waitfor(lambda:(case/'ready').exists())
            if ready:
                info=json.loads((case/'ready').read_text());known=[info['pid'],info['child']]
                start=time.monotonic();p.send_signal(sig);rc=finish(p,15)
                gone=waitfor(lambda:all(not alive(x) for x in known),2)
                check('재현',f'C1 signal {sig} rc{expected} / descendants gone / no second task',rc==expected and gone and time.monotonic()-start<17 and (case/'calls').read_text().count('\n')==1,f'rc={rc}')
                env['FAKE_MODE']='good';r=h.execute(case,env)
                check('신규',f'C1 signal {sig} releases lock',r.returncode==0)
            else: check('재현',f'C1 signal {sig} ready',False,'fake not invoked: environment failure')
        finally: cleanup_process(p,known)
    # F1 후반부: 신호 뒤 실행기가 죽으면 옛 harness 는 트랩 후 다음 과목으로 넘어간다. 새 harness 는 그 전에 끝난다.
    case,rd,env=h.case('loop_after_signal','hang',skip=False);p=launch(h.cmd(),env,case/'runner.log');known=[]
    try:
        if waitfor(lambda:(case/'ready').exists()):
            info=json.loads((case/'ready').read_text());known=[info['pid'],info['child']]
            (case/'ready').unlink();p.terminate();time.sleep(.5)
            for x in known:
                try:os.kill(x,signal.SIGKILL)
                except OSError:pass
            time.sleep(3);calls=(case/'calls').read_text().count('\n')
            check('재현','C1 after TERM + runner death no second subject starts',calls==1 and p.poll() is not None,f'calls={calls}, rc={p.poll()}')
        else: check('재현','C1 loop ready',False,'fake not invoked: environment failure')
    finally:
        more=[]
        if (case/'pid_ledger').exists():more=[pid for line in (case/'pid_ledger').read_text().splitlines() for pid in json.loads(line)]
        cleanup_process(p,known+more)
    case,rd,env=h.case('ignore_term','ignore');p=launch(h.cmd(),env,case/'runner.log');known=[]
    try:
        if waitfor(lambda:(case/'ready').exists()):
            info=json.loads((case/'ready').read_text());known=[info['pid'],info['child']]
            start=time.monotonic();p.terminate();rc=finish(p,15);elapsed=time.monotonic()-start
            check('신규','C1 TERM-ignoring runner killed after grace',rc==143 and elapsed>=9 and waitfor(lambda:all(not alive(x) for x in known),2),f'rc={rc}, seconds={elapsed:.1f}')
        else: check('신규','C1 ignoring ready',False)
    finally: cleanup_process(p,known)

def harness_lock_tests(h):
    case,rd,env=h.case('concurrent','hang');p=launch(h.cmd(),env,case/'first.log');known=[];q=None
    try:
        if not waitfor(lambda:(case/'ready').exists()): check('신규','C5 first ready',False);return
        info=json.loads((case/'ready').read_text());known=[info['pid'],info['child']];oldtmp=Path(info['tmp'])
        r=h.execute(case,env)
        check('신규','C5 contender rc3 does not touch first temp',r.returncode==3 and oldtmp.is_dir() and (case/'calls').read_text().count('\n')==1)
        p.kill();p.wait();(case/'ready').unlink();q=launch(h.cmd(),env,case/'second.log')
        ready=waitfor(lambda:(case/'ready').exists())
        new=json.loads((case/'ready').read_text()) if ready else {}
        if ready:known.extend([new['pid'],new['child']])
        check('신규','C5 KILL releases lock / distinct temp / old temp retained',ready and new['tmp']!=str(oldtmp) and oldtmp.is_dir() and (rd/'.harness.lock').is_file())
    finally:
        if q:cleanup_process(q,known)
        cleanup_process(p,known)

TRACK = r'''#!/usr/bin/env python3
import os,pathlib,signal,subprocess,time
base=pathlib.Path(os.environ['CASE'])
with (base/'tracks').open('a') as f:f.write(os.environ.get('TRACK_LABEL','harness')+'\n')
mode=os.environ.get('TRACK_MODE','return')
if mode in ('hang','ignore'):
    if mode=='ignore':signal.signal(signal.SIGTERM,signal.SIG_IGN)
    child=subprocess.Popen(['/bin/sleep','300'])
    (base/'ready').write_text(str(os.getpid())+' '+str(child.pid))
    time.sleep(300)
raise SystemExit(int(os.environ.get('TRACK_RC','0')))
'''

def full_fixture(target,label,rc=0,mode='return'):
    base=ROOT/label; base.mkdir()
    shutil.copy2(target,base/'run_full_eval.sh')
    lib=target.parent/'shared/harness/harness_lib.sh'
    if lib.exists():
        (base/'shared/harness').mkdir(parents=True);shutil.copy2(lib,base/'shared/harness/harness_lib.sh')
    write(base/'.venv/bin/activate',':\n')
    write(base/'.env','export OPENAI_API_KEY=fixture-only\n')
    write(base/'configs/load_model_config.py','print("export MODEL=fixture-model TOKENIZER=fixture-tokenizer MODEL_CLASS=fixture BASE_URL_CHAT=http://127.0.0.1:18999/v1/chat/completions BASE_URL_V1=http://127.0.0.1:18999/v1 TRACKS=\\\"harness nlu\\\"")\n')
    write(base/'bin/curl',"#!/bin/bash\nprintf '%s\\n' '{\"data\":[{\"id\":\"fixture-model\"}]}'\n",True)
    write(base/'bin/python',f'#!/bin/bash\nexec "{sys.executable}" "$@"\n',True)
    write(base/'track.py',TRACK)
    write(base/'fixture/harness/run_harness.sh',f'#!/bin/bash\nexec "{sys.executable}" "$CASE/track.py"\n',True)
    write(base/'fixture/nlu/run_nlu.sh','#!/bin/bash\necho nlu >> "$CASE/tracks"\nexit 0\n',True)
    env=envbase();env.update(CASE=str(base),PATH=str(base/'bin')+':'+env['PATH'],EVAL_TIMESTAMP='fixture_session',
        TRACK_RC=str(rc),TRACK_MODE=mode,_FULL_EVAL_REEXEC='1',LOG_DIR=str(base/'early_logs'))
    (base/'early_logs').mkdir()
    return base,env

def full_suite(target):
    for rc in (0,1,2,127,3,143):
        base,env=full_fixture(target,'rc_'+str(rc),rc)
        r=run([BASH,str(base/'run_full_eval.sh'),'fixture'],env)
        write(base/'driver.log',r.stdout)
        tracks=(base/'tracks').read_text().splitlines() if (base/'tracks').exists() else []
        expected=rc if rc in (3,143) else (0 if rc==0 else 1)
        check('재현' if rc in (3,143) else '보존',f'C5 full_eval track rc{rc}',r.returncode==expected and tracks==(['harness'] if rc in (3,143) else ['harness','nlu']),f'rc={r.returncode}, tracks={tracks}')
    if sys.platform.startswith('linux') and shutil.which('setsid') and proc_available():
        # 실제 리더 모드: _FULL_EVAL_REEXEC 없이 띄워 setsid 재실행을 타게 하고, TERM 에 그룹 정리·rc143 을 본다.
        base,env=full_fixture(target,'leader',mode='hang');env.pop('_FULL_EVAL_REEXEC',None)
        p=launch([BASH,str(base/'run_full_eval.sh'),'fixture'],env,base/'driver.log');known=[]
        try:
            ready=waitfor(lambda:(base/'ready').exists())
            if ready:known=list(map(int,(base/'ready').read_text().split()))
            m=re.search(r'PID=(\d+) PGID=(\d+)',(base/'driver.log').read_text())
            leader=bool(m) and m.group(1)==m.group(2)
            if ready:p.terminate()
            rc=finish(p,20)
            check('신규','C5 Linux setsid leader TERM cleanup',ready and leader and rc==143 and waitfor(lambda:all(not alive(x) for x in known),2),f'rc={rc}, leader={leader}')
        finally:cleanup_process(p,known)
    else:
        inconclusive('C5 Linux setsid leader','no setsid on this host; leader mode not emulated as a PASS')
    if not proc_available():
        inconclusive('C5 full_eval TERM/INT/repeated TERM/grace','ps denied: process tests not launched');return
    for label,sig,ignore,double in [('term',signal.SIGTERM,False,False),('int',signal.SIGINT,False,False),('double',signal.SIGTERM,True,True),('ignore',signal.SIGTERM,True,False)]:
        base,env=full_fixture(target,label,mode='ignore' if ignore else 'hang')
        # Default production grace is tested, including the second signal window.
        p=launch([BASH,str(base/'run_full_eval.sh'),'fixture'],env,base/'driver.log');known=[]
        try:
            if not waitfor(lambda:(base/'ready').exists()):check('신규','C5 '+label+' ready',False);continue
            known=list(map(int,(base/'ready').read_text().split()))
            start=time.monotonic();p.send_signal(sig)
            if double:
                waitfor(lambda:'trap: cleanup' in (base/'driver.log').read_text());p.terminate()
            rc=finish(p,20);elapsed=time.monotonic()-start
            expected=130 if sig==signal.SIGINT else 143
            ok=rc==expected and waitfor(lambda:all(not alive(x) for x in known),2)
            if ignore:ok=ok and elapsed>=14
            check('재현' if label=='term' else '신규','C5 '+label+' cleanup',ok,f'rc={rc}, seconds={elapsed:.1f}')
        finally:cleanup_process(p,known)
    base,env=full_fixture(target,'before_track')
    # Config loader marker occurs after traps, before a track is launched.
    write(base/'configs/load_model_config.py',"import os,pathlib,time\npathlib.Path(os.environ['CASE'],'before_ready').touch()\ntime.sleep(1)\n"+ (base/'configs/load_model_config.py').read_text())
    p=launch([BASH,str(base/'run_full_eval.sh'),'fixture'],env,base/'driver.log')
    try:
        ready=waitfor(lambda:(base/'before_ready').exists())
        if ready:p.terminate()
        rc=finish(p,7)
        check('신규','C5 TERM before first track initialized cleanup',ready and rc==143 and not (base/'tracks').exists(),f'rc={rc}')
    finally:cleanup_process(p)

def guard_fixture(target):
    base=ROOT/'guard_fixture';orch=base/'logs/resume_orch';orch.mkdir(parents=True)
    odir=base/'orchestration';(odir/'lanes').mkdir(parents=True)
    shutil.copy2(target,odir/'lane_guard.sh')
    shutil.copy2(target.parent/'lanes.conf',odir/'lanes.conf')
    (base/'shared/harness').mkdir(parents=True)
    shutil.copy2(target.parents[1]/'shared/harness/harness_lib.sh',base/'shared/harness/harness_lib.sh')
    write(base/'health','#!/bin/bash\n[ "$(cat "$CASE/health_value")" = up ]\n',True)
    write(base/'temp','#!/bin/bash\ncat "$CASE/temp_value"\n',True)
    write(base/'health_value','up');write(base/'temp_value','60 70')
    # A shell waits on an owned sleeper; fake root basename cannot match old guards.
    lane=write(odir/'lanes'/'zz_fake_lane_primary.sh','#!/bin/bash\nsleep 300 &\necho "$!" > "$CASE/lane_child"\necho ready > "$CASE/lane_ready"\nwait\n',True)
    env=envbase();env.update(CASE=str(base),LANEGUARD_STATE_DIR=str(base/'state'),LANEGUARD_LOG=str(base/'guard.log'),LANEGUARD_ONCE='1',
        LANEGUARD_LANES='fake|zz_fake_lane_primary|fixture|FIXTURE_KEY|fixture-model',
        LANEGUARD_HEALTH_CMD=str(base/'health'),LANEGUARD_TEMP_CMD=str(base/'temp'))
    return base,orch,odir,lane,env

def guard_suite(target):
    if not proc_available():
        inconclusive('C6 all real guard process assertions','ps denied: real guard and fake lanes not launched')
        guard_model(target)
        return
    base,orch,odir,lane,env=guard_fixture(target);guard=[BASH,str(odir/'lane_guard.sh')];p=None;known=[]
    def cycle(n=1):
        for _ in range(n):
            r=run(guard,env,timeout=15)
            if r.returncode:raise RuntimeError('guard cycle failed: '+r.stdout)
    def heat(value):write(base/'temp_value',value)
    def health(value):write(base/'health_value',value)
    def stopped():return 'T' in stat(p.pid)
    def state():return (base/'state/fake.state').read_text()
    def newlane():
        nonlocal p,known
        (base/'lane_ready').unlink(missing_ok=True)
        p=launch([BASH,str(lane)],env,base/f'lane_{len(OWNED)}.log')
        if not waitfor(lambda:(base/'lane_ready').exists()):raise RuntimeError('fake lane not ready')
        known=[int((base/'lane_child').read_text())]
    def reset():
        if p:cleanup_process(p,known)
        for f in (base/'state').glob('*') if (base/'state').exists() else []: f.unlink()
        health('up');heat('60 70');newlane()
    try:
        newlane();heat('90 99');cycle();check('신규','C6 heat on stops',stopped())
        health('down');cycle(2);health('up');cycle(2);check('신규','C6 server recovered but heat remains',stopped())
        heat('60 70');cycle(3);check('신규','C6 heat off x3 resumes',not stopped())
        heat('90');cycle();check('보존','C6 sensor missing → GPU-only heat stops (old temp_guard)',stopped())
        heat('60');cycle(3);check('보존','C6 sensor missing → GPU-only cool resumes',not stopped())
        health('down');cycle(2);heat('90 99');cycle();heat('60 70');cycle(3)
        check('신규','C6 reverse order server reason remains',stopped());health('up');cycle(2);check('신규','C6 reverse order both clear resumes',not stopped())
        reset();p.send_signal(signal.SIGSTOP);heat('90 99');cycle();heat('60 70');cycle(3)
        check('신규','C6 manual stop survives heat overlap',stopped())
        check('보존','C6 initially T never CONT',stopped())
        reset();heat('90 99');cycle();heat('');cycle()
        check('신규','C6 restart with unavailable temperature retains heat',stopped() and '|1|' in state().splitlines()[0])
        heat('60 70');cycle(3);check('신규','C6 restarted guard resumes held ownership',not stopped())
        # Controlled crash windows via a test-only shell function injected by
        # BASH_ENV. Production script has no crash/test hooks. exec -a keeps root match.
        hook=base/'hook.sh'
        write(hook,r'''kill() {
  if [ "$1" = -STOP ] && [ "${HOOK:-}" = before ]; then builtin kill -KILL "$$"; fi
  if [ "$1" = -STOP ] && [ "${HOOK:-}" = after ]; then builtin kill "$@"; builtin kill -KILL "$$"; fi
  if [ "$1" = -CONT ] && [ "${HOOK:-}" = fail_cont ]; then return 1; fi
  builtin kill "$@"
}
''')
        reset();heat('90 99');e=dict(env,BASH_ENV=str(hook),HOOK='before');r=run(guard,e)
        pending='|pending' in state();running=not stopped();cycle()
        check('신규','C6 pending before STOP crash / retry',r.returncode==-9 and pending and running and stopped())
        heat('60 70');cycle(2);e=dict(env,BASH_ENV=str(hook),HOOK='fail_cont');run(guard,e)
        check('신규','C6 CONT failure retains held entry',stopped() and '|held' in state());cycle();check('신규','C6 CONT retry next cycle',not stopped())
        reset();heat('90 99');e=dict(env,BASH_ENV=str(hook),HOOK='after');r=run(guard,e)
        cycle();heat('60 70');cycle(4)
        text=(base/'guard.log').read_text();check('신규','C6 pending+T ambiguous / single warning / no CONT',r.returncode==-9 and stopped() and '|ambiguous' in state() and text.count('pending+T')==1)
        reset();q=launch([BASH,str(lane)],env,base/'duplicate.log');qkids=[]
        try:
            waitfor(lambda:len(run(['/usr/bin/pgrep','-P',str(q.pid)]).stdout.split())>0)
            qkids=descendants(q.pid)[1:];heat('90 99');cycle(2)
            check('신규','C6 duplicate roots receive no signals',not stopped() and 'T' not in stat(q.pid) and '레인 2개 이상' in (base/'guard.log').read_text())
        finally:cleanup_process(q,qkids)
        # A sh command containing the pattern must not count as another bash lane.
        q=launch(['/bin/sh','-c','sleep 300','zz_fake_lane_primary'],env,base/'decoy.log');qkids=[]
        try:
            qkids=descendants(q.pid)[1:];cycle();check('보존','C6 sh -c decoy excluded','T' not in stat(q.pid) and stopped())
        finally:cleanup_process(q,qkids)
        # C7: each unsupported command is observed beside the valid root.
        elsewhere=write(base/'elsewhere/lanes'/lane.name,lane.read_text(),True)
        for label,args in [('outside orchestration',[BASH,str(elsewhere)]),
                           ('extra argument',[BASH,str(lane),'extra']),
                           ('bash -c',[BASH,'-c','sleep 300',lane.stem])]:
            q=launch(args,env,base/('c7_'+str(len(OWNED))+'.log'));qkids=[]
            try:
                ready=waitfor(lambda:bool(stat(q.pid)) if label=='bash -c' else len(descendants(q.pid))>1)
                qkids=descendants(q.pid)[1:]
                before=(base/'guard.log').read_text()
                heat('90 99');cycle()
                added=(base/'guard.log').read_text()[len(before):]
                pids=[q.pid,*qkids]
                check('신규','C7 '+label+' excluded / zero signals',ready and
                      all(stat(pid) and 'T' not in stat(pid) for pid in pids) and
                      not any(re.search(r'(?:STOP|CONT) pid='+str(pid)+r' ',added) for pid in pids) and
                      '레인 2개 이상' not in added and stopped())
            finally:cleanup_process(q,qkids)
        # Replace root while old ownership exists: counts restart, new running
        # process must not receive a CONT intended for the old PID.
        cleanup_process(p,known);heat('');health('up');newlane();cycle()
        fields=state().splitlines()[0].split('|')
        check('신규','C6 root change resets consecutive counters',fields[-3:]==['0','1','0'])
        check('신규','C6 new root never gets old CONT',f'CONT pid={p.pid} ' not in (base/'guard.log').read_text())
        # Simulate a child created between snapshots by letting an already-owned
        # child resume and spawn while root stays T, then reconcile again.
        reset()
        # Install a child spawner before launching the lane, it polls its marker.
        cleanup_process(p,known)
        write(lane,'#!/bin/bash\n/bin/bash "$CASE/spawner.sh" &\necho "$!" > "$CASE/lane_child"\necho ready > "$CASE/lane_ready"\nwait\n')
        write(base/'spawner.sh','#!/bin/bash\nwhile [ ! -f "$CASE/spawn" ]; do sleep 0.05; done\nsleep 300 &\necho "$!" > "$CASE/new_child"\nwait\n')
        newlane();heat('90 99');cycle()
        for child_pid in descendants(known[0]): os.kill(child_pid,signal.SIGCONT)
        write(base/'spawn','go')
        ready=waitfor(lambda:(base/'new_child').exists());extra=int((base/'new_child').read_text()) if ready else 0
        if extra:known.append(extra)
        cycle();check('신규','C6 new descendant stopped on next cycle',ready and 'T' in stat(extra))
        # Singleton lock is tested with an owned lock holder, not production ORCH.
        holder=launch([BASH,'-c','exec 9>"$1"; if command -v flock >/dev/null; then flock -n 9; else /usr/bin/lockf -s -t 0 9; fi; echo ready > "$2"; sleep 300','lock',str(orch/'.lane_guard.lock'),str(base/'lock_ready')],env,base/'lock.log');holderkids=[]
        try:
            waitfor(lambda:(base/'lock_ready').exists());holderkids=descendants(holder.pid)[1:]
            r=run(guard,env);check('신규','C6 singleton lock rc3',r.returncode==3)
        finally:cleanup_process(holder,holderkids)
    finally:
        if p:cleanup_process(p,known)

    guard_default_lanes(base,odir,env)

def guard_default_lanes(base,odir,env):
    default_env=dict(env)
    default_env.pop('LANEGUARD_LANES',None)
    default_env['LANEGUARD_ONCE']='1'
    before=(base/'guard.log').read_text() if (base/'guard.log').exists() else ''
    r=run([BASH,str(odir/'lane_guard.sh')],default_env)
    added=(base/'guard.log').read_text()[len(before):]
    check('신규','C8 default lanes.conf without LANEGUARD_LANES',r.returncode==0 and
          all(name+': 레인 식별 root=없음' in added for name in ('qwen38','qwenfp8')),f'rc={r.returncode}')

def real_cancel(target,python):
    if not proc_available():
        inconclusive('C1 real lm_eval','process inspection denied; no socket/runner launched');return
    # Bind before launching any model process, never use remote endpoint defaults.
    listener=socket.socket();listener.settimeout(.2)
    try:listener.bind(('127.0.0.1',18999));listener.listen()
    except OSError as e:listener.close();inconclusive('C1 real lm_eval bind',str(e));return
    case=ROOT/'real';case.mkdir();env=envbase();env.update(MODEL_TEST_BASE=str(case),EVAL_TIMESTAMP='real_cancel',
        TASKS_OVERRIDE='kmmlu_think_accounting',LIMIT='2',LM_EVAL_BIN=str(python)+' -m lm_eval',NUM_CONCURRENT='1')
    if shutil.which('lsof') is None:listener.close();inconclusive('C1 real lm_eval','lsof unavailable');return
    # Offline flags prevent dataset/tokenizer downloads. Missing caches are an
    # environmental INCONCLUSIVE, never an invitation to access the network.
    p=launch([BASH,str(target),'fixture-model','fixture-tokenizer','http://127.0.0.1:18999/v1/chat/completions'],env,case/'runner.log')
    conn=None;known=[]
    try:
        deadline=time.monotonic()+60
        while p.poll() is None and time.monotonic()<deadline:
            try:conn,_=listener.accept();break
            except socket.timeout:pass
        listing=run(['lsof','-nP','-iTCP:18999']).stdout
        known=descendants(p.pid)[1:] if p.poll() is None else []
        write(case/'process_snapshot.json',json.dumps({'root':p.pid,'children':known,'lsof':listing},indent=2))
        if conn is None or str(p.pid) not in listing and not any(str(x) in listing for x in known):
            inconclusive('C1 real lm_eval ready','no verified socket connection within 60s; inspect runner.log/offline cache');return
        p.terminate();rc=finish(p,15)
        check('신규','C1 real lm_eval rc143 / snapshot descendants gone',rc==143 and waitfor(lambda:all(not alive(x) for x in known),2),f'rc={rc}')
        lock=case/'results/fixture_model/real_cancel/language/harness/.harness.lock'
        r=shell_function(target.parent/'harness_lib.sh','harness_lock',lock)
        check('신규','C1 real lm_eval lock released',r.returncode==0)
    finally:
        cleanup_process(p,known)
        if conn:conn.close()
        listener.close()

# Supplementary model tests: run the actual guard against fixture-only ps/pgrep/
# kill adapters. They never deliver OS signals and do NOT substitute for C6 real
# process tests. This isolates state logic when the sandbox denies process reads.
MODEL_PROCESS = r'''import json,os,pathlib,re,sys
p=pathlib.Path(os.environ['CASE'])/'processes.json';d=json.loads(p.read_text());a=sys.argv[1:];tool=a.pop(0)
if tool=='pgrep':
    mode,value=a; hits=[]
    for pid,x in d['processes'].items():
        if mode=='-P' and str(x['ppid'])==value or mode=='-f' and re.search(value,x['cmd']):hits.append(pid)
    print('\n'.join(hits));sys.exit(0 if hits else 1)
if tool=='ps':
    if '-axo' in a:print('\n'.join(x['cmd'] for x in d['processes'].values()));sys.exit(0)
    pid=a[a.index('-p')+1];field=a[a.index('-o')+1]
    if field=='pid=':print(pid);sys.exit(0)
    x=d['processes'].get(pid)
    if not x:sys.exit(1)
    print(x[{'lstart=':'stamp','stat=':'stat','command=':'cmd'}[field]]);sys.exit(0)
if tool=='kill':
    sig,pid=a;x=d['processes'].get(pid)
    if not x:sys.exit(1)
    d['signals'].append([sig,pid]);rc=0
    if sig=='-STOP':x['stat']='T'
    elif sig=='-CONT':
        if d.get('fail_cont'):rc=1
        else:x['stat']='S'
    p.write_text(json.dumps(d));sys.exit(rc)
'''

def guard_model(target):
    base,orch,odir,lane,env=guard_fixture(target)
    model=write(base/'process_model.py',MODEL_PROCESS)
    bindir=base/'model_bin'
    for tool in ('ps','pgrep'):
        write(bindir/tool,f'#!/bin/bash\nexec "{sys.executable}" "$CASE/process_model.py" {tool} "$@"\n',True)
    hook=write(base/'model_hook.sh',f'kill() {{ "{sys.executable}" "$CASE/process_model.py" kill "$@"; }}\n')
    env.update(PATH=str(bindir)+':'+env['PATH'],BASH_ENV=str(hook))
    table=base/'processes.json';file=base/'state/fake.state'
    root='800001';child='800002'
    def fresh():
        d={'processes':{root:{'ppid':0,'stamp':'Fri Oct  9 12:00:00 2026','stat':'S','cmd':'/bin/bash '+str(lane)},
                        child:{'ppid':int(root),'stamp':'Fri Oct  9 12:00:01 2026','stat':'S','cmd':'sleep 300'}},'signals':[]}
        write(table,json.dumps(d));file.unlink(missing_ok=True);write(base/'health_value','up');write(base/'temp_value','60 70')
    def load():return json.loads(table.read_text())
    def store(d):write(table,json.dumps(d))
    def temp(x):write(base/'temp_value',x)
    def health(x):write(base/'health_value',x)
    def stopped():return load()['processes'][root]['stat']=='T'
    def cycle(n=1):
        for _ in range(n):
            r=run([BASH,str(odir/'lane_guard.sh')],env)
            if r.returncode:raise RuntimeError('guard model cycle: '+r.stdout)
    def pending(t):
        d=load();d['processes'][root]['stat']='T' if t else 'S';store(d)
        write(file,f"state|{root}:{d['processes'][root]['stamp']}|0|1|0|0|0\nwarnings|0|0\n{root}|{d['processes'][root]['stamp']}|pending\n")
    fresh();temp('90 99');cycle();check('신규','C6 MODEL heat STOP all descendants',all(x['stat']=='T' for x in load()['processes'].values()))
    health('down');cycle(2);health('up');cycle(2);check('신규','C6 MODEL server up retains heat stop',stopped())
    temp('60 70');cycle(3);d=load();cont=[x[1] for x in d['signals'] if x[0]=='-CONT']
    check('신규','C6 MODEL heat clear resumes children before root',not stopped() and cont==[child,root])
    fresh();health('down');cycle(2);temp('90 99');cycle();temp('60 70');cycle(3)
    check('신규','C6 MODEL reverse order server still holds',stopped());health('up');cycle(2);check('신규','C6 MODEL reverse both clear',not stopped())
    fresh();d=load();d['processes'][root]['stat']='T';store(d);temp('90 99');cycle();temp('60 70');cycle(3)
    check('신규','C6 MODEL manual T never CONT',stopped() and ['-CONT',root] not in load()['signals'])
    fresh();temp('90 99');cycle();temp('');cycle();check('신규','C6 MODEL restart sensor unavailable retains heat',stopped() and '|0|1|' in file.read_text().splitlines()[0])
    temp('60 70');cycle(3);check('신규','C6 MODEL restart recovers held entries',not stopped())
    fresh();pending(False);temp('90 99');cycle();check('신규','C6 MODEL pending non-T is removed and restopped',stopped() and '|pending' not in file.read_text() and '|held' in file.read_text())
    fresh();pending(True);temp('');cycle();temp('60 70');cycle(4)
    check('신규','C6 MODEL pending+T ambiguous once and never CONT',stopped() and '|ambiguous' in file.read_text() and (base/'guard.log').read_text().count('pending+T')==1)
    fresh();temp('90 99');cycle();temp('60 70');cycle(2);d=load();d['fail_cont']=True;store(d);cycle()
    check('신규','C6 MODEL CONT failure retains held',stopped() and '|held' in file.read_text());d=load();d['fail_cont']=False;store(d);cycle();check('신규','C6 MODEL CONT retried',not stopped())
    fresh();d=load();d['processes']['800003']=dict(d['processes'][root],stamp='second root');store(d);temp('90 99');cycle(2)
    check('신규','C6 MODEL duplicate roots no signal / warning once',not load()['signals'] and (base/'guard.log').read_text().count('레인 2개 이상')==1)
    fresh();d=load();d['processes']['800003']={'ppid':0,'stamp':'decoy','stat':'S','cmd':'sh -c bash '+str(lane)};store(d);temp('90 99');cycle()
    check('보존','C6 MODEL sh decoy excluded',stopped() and load()['processes']['800003']['stat']=='S')
    saved=load();saved_state=file.read_text()
    for label,cmd in [('outside orchestration','/bin/bash '+str(base/'elsewhere/lanes'/lane.name)),
                      ('extra argument','/bin/bash '+str(lane)+' extra'),
                      ('bash -c',"/bin/bash -c sleep 300 "+lane.stem)]:
        fresh();d=load();d['processes']={root:dict(d['processes'][root],cmd=cmd)};store(d)
        temp('90 99');cycle()
        check('신규','C7 MODEL '+label+' excluded / zero signals',not load()['signals'] and not stopped())
    store(saved);write(file,saved_state)
    d=load();d['processes']['800004']={'ppid':int(child),'stamp':'new child','stat':'S','cmd':'sleep 300'};store(d);cycle()
    check('신규','C6 MODEL new descendant reconciled',load()['processes']['800004']['stat']=='T')
    d=load();d['processes'][root]['stamp']='new incarnation';d['processes'][root]['stat']='S';store(d);temp('');cycle()
    check('신규','C6 MODEL instance change counters reset and no stale CONT',file.read_text().splitlines()[0].endswith('|0|1|0') and ['-CONT',root] not in load()['signals'])
    # Root absence must still reconcile stored orphan ownership when reasons clear.
    d=load();del d['processes'][root];d['processes'][child]['ppid']=1;store(d);temp('60 70');cycle(3)
    check('신규','C6 MODEL orphan held descendant resumes without root',load()['processes'][child]['stat']=='S')

    store({"processes":{},"signals":[]})
    guard_default_lanes(base,odir,env)

def main():
    global ROOT
    parser=argparse.ArgumentParser();parser.add_argument('suite',choices=('harness','full','guard','real'));parser.add_argument('target',type=Path);parser.add_argument('--python',type=Path)
    args=parser.parse_args();args.target=args.target.resolve()
    if not args.target.is_file():parser.error('target script missing')
    ROOT=Path(tempfile.mkdtemp(prefix=args.suite+'_',dir=WORK))
    print('ARTIFACTS='+str(ROOT),flush=True)
    try:
        if args.suite=='harness':harness_suite(args.target)
        elif args.suite=='full':full_suite(args.target)
        elif args.suite=='guard':guard_suite(args.target)
        else:real_cancel(args.target,args.python or WORKSPACE/'foundation_model_test_non_thinking/.venv/bin/python')
    except Exception as e:
        check('신규','driver exception',False,repr(e))
        raise
    finally:
        for p in OWNED:
            if p.poll() is None:cleanup_process(p)
        summary={'pass':PASSES,'fail':FAILURES,'inconclusive':INCONCLUSIVE}
        write(ROOT/'summary.json',json.dumps(summary,indent=2))
        print('SUMMARY '+json.dumps(summary),flush=True)
    return 1 if FAILURES else (77 if not PASSES and INCONCLUSIVE else 0)

if __name__=='__main__':sys.exit(main())
