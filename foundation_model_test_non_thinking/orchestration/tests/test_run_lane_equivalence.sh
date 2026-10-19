#!/bin/bash
set -u
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
exec python3 -I - "$HERE/.." <<'PY'
import difflib
import http.server
import json
import os
from pathlib import Path
import re
import shutil
import subprocess as sp
import sys
import tempfile
import threading

orch=Path(sys.argv[1]).resolve()
repo=orch.parent
counts={'pass':0,'fail':0,'inconclusive':0}
def check(name,ok,detail=''):
    counts['pass' if ok else 'fail']+=1
    print(('PASS ' if ok else 'FAIL ')+name+(' — '+detail if detail else ''),flush=True)
def run(args,env,cwd):
    return sp.run(args,env=env,cwd=cwd,stdout=sp.PIPE,stderr=sp.STDOUT,timeout=30)
def put(path,text):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(text)

def main():
    fx=Path(tempfile.mkdtemp(prefix='lane_equivalence_')).resolve()
    print('ARTIFACTS='+str(fx),flush=True)
    (fx/'.venv').symlink_to(repo/'.venv',target_is_directory=True)
    (fx/'configs').symlink_to(repo/'configs',target_is_directory=True)
    # 4d: fixture preparation only; use the actual frozen lock helper.
    (fx/'shared/harness').mkdir(parents=True)
    (fx/'shared/harness/harness_lib.sh').symlink_to(repo/'shared/harness/harness_lib.sh')
    # Synthetic credentials only; never open the repository .env.
    put(fx/'.env','OPENAI_API_KEY=fixture-one\nOPENAI_API_KEY_7=fixture-seven\nTAUBENCH_USER_API_KEY=fixture-user\n')
    (fx/'orchestration/lanes').mkdir(parents=True)
    (fx/'orchestration/run_lane.sh').symlink_to(orch/'run_lane.sh')
    # 5a: the common entry now sources track definitions from its fixture HERE.
    (fx/'orchestration/tracks').symlink_to(orch/'tracks',target_is_directory=True)
    stub='''#!/bin/bash
set -u
{
  printf 'argv=%s\\n' "$@"
  printf 'cwd=%s\\n' "$PWD"
  # 4d: both sides record fd 9; it must be closed in evaluation children.
  if { : >&9; } 2>/dev/null; then printf 'fd9=open\\n'; else printf 'fd9=closed\\n'; fi
  env | LC_ALL=C sort | awk '!/^(SHLVL|OLDPWD|PWD|LANE_DRY_RUN|__CF_USER_TEXT_ENCODING|_)=/ && !/^BASH_FUNC_/'
} > "$MODEL_TEST_BASE/dump/$EVAL_TIMESTAMP.txt"
printf '%s\\n' "$EVAL_TIMESTAMP" >> "$MODEL_TEST_BASE/calls"
printf 'STUB_OUT %s\\n' "$EVAL_TIMESTAMP"
printf 'STUB_ERR %s\\n' "$EVAL_TIMESTAMP" >&2
if [ -f "$MODEL_TEST_BASE/rc/$EVAL_TIMESTAMP" ]; then exit "$(cat "$MODEL_TEST_BASE/rc/$EVAL_TIMESTAMP")"; fi
exit 0
'''
    put(fx/'vsm/harness/run_harness.sh',stub)
    put(fx/'vsm/taubench/run_taubench.sh',stub)
    lanes=[('qwen38','run_qwen38_27b_kmmlu_nothink.sh','qwen_qwen3.8_27b','kmmlu_nothink_20261011'),
           ('qwenfp8','run_qwenfp8_27b_kmmlu_nothink.sh','qwen_qwen3.8_27B_FP8','kmmlu_nothink_20261010'),
           ('diffusion_tbstd4','run_diffusion_tbstd4.sh','google_diffusiongemma_26B_A4B_it','tbstd4_20261011')]
    for name,legacy,model,session in lanes:
        kmmlu=name!='diffusion_tbstd4'
        tok=fx/'tok'/name
        put(tok/'chat_template.jinja','{% set enable_thinking = false %}\n')
        link=fx/'orchestration/lanes'/f'{name}.sh';link.symlink_to('../run_lane.sh')
        if kmmlu:
            original=(orch/'lanes'/f'{name}.conf').read_text()
            changed,n=re.subn(r'^LANE_TOKENIZER=.*$',lambda m:'LANE_TOKENIZER='+str(tok),original,flags=re.M)
            check(name+' conf tokenizer substitution exactly one line',n==1)
            put(link.with_suffix('.conf'),changed)
        else:
            put(link.with_suffix('.conf'),'''CONFIG=google_diffusiongemma_26B_A4B_it
HOST_ENV=DIFF_HOST
HOST_DEFAULT=192.168.0.8:18023
KEYVAR=OPENAI_API_KEY
TRACK=taubench_std4
SESSION=tbstd4_20261011
LABEL="diffusiongemma taubench standard×4"
PREFIX="diffusion tbstd4"
END_LABEL="diffusiongemma taubench standard×4"
''')
        original=(orch/'tests/legacy'/legacy).read_text()
        changed,n=re.subn(r'^BASE=.*$',lambda m:'BASE='+str(fx),original,flags=re.M)
        assert n==1
        if kmmlu:
            changed,n=re.subn(r'^TOK=.*$',lambda m:'TOK='+str(tok),changed,flags=re.M)
            assert n==1
        old=fx/'legacy'/legacy;put(old,changed)
        diff=sp.run(['diff',str(orch/'tests/legacy'/legacy),str(old)],stdout=sp.PIPE,text=True)
        lines=[x for x in diff.stdout.splitlines() if x.startswith(('<','>'))]
        check(name+' legacy only BASE/TOK substitutions',diff.returncode==1 and len(lines)==(4 if kmmlu else 2))

    state={'status':200,'model':''}
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path!='/v1/models':
                self.send_error(404);return
            self.send_response(state['status']);self.end_headers()
            self.wfile.write(json.dumps({'data':[{'id':state['model']}]},separators=(',',':')).encode())
        def log_message(self,*args):pass
    try:
        server=http.server.HTTPServer(('127.0.0.1',0),Handler)
    except OSError as e:
        counts['inconclusive']+=1
        print('INCONCLUSIVE TCP bind: '+str(e),flush=True)
        return
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    env={k:os.environ[k] for k in ('HOME','USER','LANG','PATH') if k in os.environ}
    env.update(LC_ALL='C',PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',HF_DATASETS_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    endpoint='127.0.0.1:'+str(server.server_port)
    env.update(QWEN38_HOST=endpoint,QWENFP8_HOST=endpoint,DIFF_HOST=endpoint)
    try:
        for name,legacy,model,session in lanes:
            kmmlu=name!='diffusion_tbstd4'
            sessions=[session+'_r'+str(i) for i in (1,2,3)] if kmmlu else [session]
            logname='harness_'+model+'.log' if kmmlu else 'taubench_std4.log'
            scenarios=['success','rc','http500','wrong_model']+(['template'] if kmmlu else [])
            for scenario in scenarios:
                results=[]
                for side,script in [('old',fx/'legacy'/legacy),('new',fx/'orchestration/lanes'/f'{name}.sh')]:
                    for directory in ('logs','dump','rc'):
                        shutil.rmtree(fx/directory,ignore_errors=True);(fx/directory).mkdir()
                    (fx/'calls').unlink(missing_ok=True)
                    put(fx/'logs/resume_orch/orchestrator.log','')
                    for ts in sessions:put(fx/'logs'/ts/logname,'SENTINEL\n')
                    put(fx/'tok'/name/'chat_template.jinja','no disabled thinking here\n' if scenario=='template' else '{% set enable_thinking = false %}\n')
                    state.update(status=500 if scenario=='http500' else 200,model='other-model' if scenario=='wrong_model' else model)
                    expected_rc=(1 if kmmlu else 3) if scenario=='rc' else (0 if scenario=='success' else 1)
                    if scenario=='rc':put(fx/'rc'/sessions[0],str(expected_rc))
                    r=run(['/bin/bash',str(script)],env,fx)
                    dump={p.name:p.read_bytes() for p in (fx/'dump').glob('*.txt')}
                    if side=='new':
                        # Only the host lock file is new; old argv/env/log assertions below remain unchanged.
                        assert len(list((fx/'logs/resume_orch').glob('.lane_host_*.lock')))==1
                        assert all(b'fd9=closed\n' in data for data in dump.values())
                    calls=(fx/'calls').read_text().splitlines() if (fx/'calls').exists() else []
                    logs={ts:(fx/'logs'/ts/logname).read_bytes() for ts in sessions}
                    messages=re.sub(r'^\[\d\d-\d\d \d\d:\d\d:\d\d\] ','',(fx/'logs/resume_orch/orchestrator.log').read_text(),flags=re.M)
                    want=sessions if scenario=='success' else (sessions[:1] if scenario=='rc' else [])
                    check(f'{name}/{scenario}/{side} rc and call order',r.returncode==expected_rc and calls==want,f'rc={r.returncode}, calls={len(calls)}')
                    check(f'{name}/{scenario}/{side} append + stdout/stderr order',all(logs[ts]==('SENTINEL\n'+(f'STUB_OUT {ts}\nSTUB_ERR {ts}\n' if ts in want else '')).encode() for ts in sessions))
                    results.append((r.returncode,dump,messages,logs))
                    artifact=fx/'evidence'/name/scenario/side
                    put(artifact/'stdout.txt',r.stdout.decode(errors='replace'))
                    put(artifact/'orchestrator.txt',messages)
                    for ts,data in dump.items():
                        (artifact/ts).write_bytes(data)
                old,new=results
                check(f'{name}/{scenario} identical dump bytes',old[1]==new[1])
                check(f'{name}/{scenario} identical orchestrator lines',old[2]==new[2])
                check(f'{name}/{scenario} identical exit and log bytes',old[0]==new[0] and old[3]==new[3])
    finally:
        server.shutdown();server.server_close();thread.join(timeout=2)
try:
    main()
except Exception as e:
    check('driver exception',False,repr(e))
finally:
    print('SUMMARY '+json.dumps(counts),flush=True)
sys.exit(1 if counts['fail'] else 77 if counts['inconclusive'] else 0)
PY
