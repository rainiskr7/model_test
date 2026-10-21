"""무엇: kosgd2 shell 순서/중지 · 입력: 기존 가짜 PY · 출력: 전송·순서·정지 단언 · 계약 §7-4b·7-4d."""

import shlex
import subprocess
import pytest
from tests.ops.test_readonly import snapshot
from tests.ops.test_lane import test_live_lane_lock_and_stop_now as check_live_stop
from tests.run.file_support import put_yaml


@pytest.mark.parametrize('kind', ['systemone', 'b1'])
@pytest.mark.parametrize('scoring', ['separate', 'joint'])
def test_dry_run_registration_order_and_no_writes(sandbox, kind, scoring):
    put_yaml(sandbox.root / 'configs/models/model.yaml', dict(kind=kind, served_name='synthetic',
        auth_env='SYNTHETIC_KEY', question_scoring=scoring))
    before = snapshot(sandbox.root)
    result = sandbox.run(SETS='kosgd2', OPS_DRY_RUN='1')
    assert result.returncode == 0, result.stdout + result.stderr
    commands = [shlex.split(line) for line in result.stdout.splitlines() if line.startswith('DRY ') and ' -c ' in line]
    commands = [c[c.index('-c')+2:] for c in commands]
    assert [c[0] for c in commands] == ['run', 'run', 'threshold', 'threshold',
        'question-threshold', 'question-threshold', 'score-variants', 'score-variants', 'run', 'run',
        'score', 'certify', 'score', 'certify', 'question-risk', 'score-variants', 'question-risk', 'score-variants']
    assert all(c[1] == 'threshold' for c in commands[6:8])
    assert [c[c.index('--stage')+1] for c in commands if c[0] == 'run'] == ['dev', 'dev', 'test', 'test']
    for c in (commands[1], commands[9]):
        assert ('--offline' in c) == (scoring == 'separate')
        assert '--base-url' not in c if scoring == 'separate' else '--base-url' in c
    assert snapshot(sandbox.root) == before
    assert not sandbox.calls.exists() and not sandbox.curls.exists()


@pytest.mark.parametrize('command', ['run', 'threshold', 'question-threshold', 'score-variants', 'score', 'certify', 'question-risk'])
def test_failure_never_runs_following_stage(sandbox, command):
    result = sandbox.run(SETS='kosgd2', FAIL_COMMAND=command)
    assert result.returncode == 7
    calls = sandbox.commands()
    assert calls[-1][0] == command
    if command in ('run', 'threshold', 'question-threshold', 'score-variants'):
        assert not any('--stage' in c and c[c.index('--stage')+1] == 'test' for c in calls)
    if command == 'run': assert len(calls) == 3


def test_preflight_damage_and_stop_have_no_evaluation_calls(sandbox):
    directory = sandbox.root / 'results/model/r1/A/kosgd2/actions_only'
    directory.mkdir(parents=True)
    (directory / 'fingerprint.json').write_text('{}')
    before = snapshot(directory)
    assert sandbox.run(SETS='kosgd2').returncode != 0
    assert not sandbox.commands() and not sandbox.curls.exists()
    assert snapshot(directory) == before
    assert sandbox.run('stop', ['model']).returncode == 0
    assert sandbox.run(SETS='kosgd2').returncode == 4


def test_kosgd2_live_lock_and_stop_now(sandbox):
    sandbox.env['SETS'] = 'kosgd2'
    check_live_stop(sandbox)


@pytest.mark.parametrize('action,code', [('create', 9), ('skip', 0), ('stop', 7)])
@pytest.mark.parametrize('phase', ['dev', 'threshold', 'variant-threshold'])
def test_shared_action_guard_preserves_skip_and_exit_status(sandbox, action, code, phase):
    script = '''
source "$1"
requested=$2 phase=$3
kosgd2_action() { [ "$requested" != stop ] || return 7; printf '%s\\n' "$requested"; }
log() { :; }
dir_of() { printf /synthetic; }
run_stage() { printf 'run %s %s' "$1" "$2"; return 9; }
step() { printf 'step'; printf ' %s' "$@"; return 9; }
if [ "$phase" = dev ]; then kosgd2_stage task "$phase"; else kosgd2_threshold task "$phase"; fi
'''
    result = subprocess.run(['bash', '-c', script, 'test', str(sandbox.root / 'ops/kosgd2_steps.sh'),
                             action, phase], capture_output=True, text=True, env=sandbox.env)
    assert result.returncode == code
    expected = {'dev': 'run task dev', 'threshold': 'step local threshold --run-dir /synthetic',
                'variant-threshold': 'step local score-variants threshold --run-dir /synthetic'}
    assert result.stdout == (expected[phase] if action == 'create' else '')
