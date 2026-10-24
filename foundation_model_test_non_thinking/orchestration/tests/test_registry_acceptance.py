"""CB1/CB2/CB3: local registration, isolated guard identity, and byte preservation."""
import json
import re

import pytest

from orchestration.tests.laneconf_support import REPO, SAMPLE, assignments
from orchestration.tests.lane_guard_check.fixture import Fixture as GuardFixture
from orchestration.tests.lane_guard_check.model_cases import process
from orchestration.tests.registry_support import (
    REGISTRY_BASELINE, RegistryComparison, common_hashes, with_completion_check,
)

LANES = [(model, 'kmmlu') for model in ('qwen38', 'qwenfp8', 'qwen35fp8', 'qwen36')] + [('qwen35fp8', 'full')]


def test_cb1_demo_registration_and_removal_are_local(tmp_path):
    guard = GuardFixture(REPO, tmp_path / 'checkout', REPO / 'orchestration/lane_guard.sh')
    fx = RegistryComparison(guard.base)
    fx.put('orchestration/models/sample.conf', SAMPLE)
    (fx.base / '.env').unlink()
    before = common_hashes(fx.orch)
    demo = fx.put('orchestration/tracks/demo.sh',
                  'track_dry_run() { printf "DEMO SESSION=%s\\n" "$SESSION"; }\n'
                  'track_run() { :; }\n')  # CH4: both hooks are now required, including dry-run.
    (fx.orch / 'lanes/demo.sh').symlink_to('../run_lane.sh')
    fx.put('orchestration/models/sample.conf', SAMPLE + 'SESSION_DEMO=local_demo\n')
    lane = fx.lane('sample', 'demo')
    fx.evidence('CB1/dry', lane)
    assert lane.returncode == 0 and lane.stderr == b''
    assert lane.stdout.splitlines()[-1] == b'DEMO SESSION=local_demo'
    assert len(lane.stdout.splitlines()) == 4
    assert not (fx.base / '.env').exists()
    fx.assert_dry()
    guard.env['LANEGUARD_LANES'] = 'sample_demo|demo|sample|fixture.invalid|FIXTURE_KEY|fixture-model'
    command = f'/bin/bash {fx.orch}/lanes/demo.sh sample'
    guard.table({'800001': process(command), '800002': process(command + '_other'),
                 '800003': process(command + ' extra'),
                 '800009': process(command.replace(str(fx.base), str(tmp_path / 'outside')))})
    guard.cycle()
    assert 'sample_demo: 레인 식별 root=800001 ' in guard.log()
    assert (fx.base / 'state/sample_demo.state').read_text().startswith('state|800001:')
    assert not guard.signals()
    demo.unlink()
    rejected = fx.lane('sample', 'demo')
    fx.evidence('CB1/removed', rejected)
    assert (rejected.returncode, rejected.stdout, rejected.stderr) == (2, b'', b'run_lane: unknown TRACK: demo\n')
    with pytest.raises(RuntimeError, match='guard rc=4:'):
        guard.cycle()
    assert not guard.signals() and not (fx.base / 'network_attempts').exists()
    assert common_hashes(fx.orch) == before
    (fx.base / 'common_hashes.json').write_text(json.dumps({'before': before, 'after': common_hashes(fx.orch)}, indent=2))
    print(f'CB1 dry/identity/removal/common hashes: {fx.base}')


def test_cb2_common_code_has_no_fixed_track_names_or_comparisons():
    paths = [REPO / 'orchestration/run_lane.sh', REPO / 'orchestration/lane_guard.sh',
             *sorted((REPO / 'orchestration/laneconf').glob('*.py'))]
    for path in paths:
        text = path.read_text()
        # There currently are no exemptions needed, even for comments/docstrings.
        assert not re.search(r'kmmlu|taubench_std4|\bfull\b', text), path
    assert not re.search(r'\$TRACK" (=|!=)', paths[0].read_text())


@pytest.mark.parametrize('model,track', LANES)
def test_cb3_five_lanes_match_bundle_b_head_bytes(tmp_path, model, track):
    fx = RegistryComparison(tmp_path / 'checkout')
    fx.put(f'orchestration/models/{model}.conf', (REPO / f'orchestration/models/{model}.conf').read_text())
    (fx.base / '.env').unlink()
    # Do not rely on the calling pytest disabling bytecode; CLI itself must use -B.
    fx.env.pop('PYTHONDONTWRITEBYTECODE')
    outputs = []
    for side in ('HEAD', 'working'):
        fx.install(side)
        result = fx.lane(model, track)
        fx.evidence('CB3/' + side, result)
        assert result.returncode == 0, result.stderr
        outputs.append((result.stdout, result.stderr, result.returncode))
        fx.assert_dry()
    stdout, stderr, rc = with_completion_check(outputs[0])
    stdout = b''.join(line.rstrip(b'\n') + b' --judge-model openai/gpt-4.1-mini\n'
                      if b'shared.functionchat.judge.run_judge ' in line else line
                      for line in stdout.splitlines(keepends=True))
    assert (stdout, stderr, rc) == outputs[1]
    print(f'CB3 {model}/{track} HEAD={REGISTRY_BASELINE} bytes equal except C7 follow-up: {fx.base}/evidence')


@pytest.mark.parametrize('track', ['kmmlu', 'full'])
@pytest.mark.parametrize('change', ['unknown', 'duplicate', 'prefix', 'empty', 'cr', 'no_lf', 'equals', 'space'])
def test_cb3_config_paths_match_bundle_b_head_bytes(tmp_path, track, change):
    fx = RegistryComparison(tmp_path / 'checkout')
    base = SAMPLE + 'SESSION_FULL=full_fixture\n'
    cases = {
        'unknown': base + 'UNKNOWN=x\n', 'duplicate': base + 'HOST_DEFAULT=second\n',
        'prefix': base + 'FULL_LANE_DISPLAY=x\n', 'empty': base.replace('LANE_DISPLAY=fixture', 'LANE_DISPLAY='),
        'cr': base.replace('LANE_DISPLAY=fixture\n', 'LANE_DISPLAY="fixture"\r\n'),
        'no_lf': base.rstrip('\n'), 'equals': base.replace('LANE_TOKENIZER=unused', 'LANE_TOKENIZER=a=b'),
        'space': base + ' REPS=2\n',
    }
    fx.put('orchestration/models/sample.conf', cases[change])
    outputs = []
    for side in ('HEAD', 'working'):
        fx.install(side)
        result = fx.lane('sample', track)
        fx.evidence('CB3/' + side, result)
        outputs.append((result.stdout, result.stderr, result.returncode))
    if change in ('prefix', 'empty'):
        # Only these diagnostic bytes intentionally change with the conf key.
        message = 'key cannot have track prefix' if change == 'prefix' else 'required key'
        assert outputs[0] == (b'', f'run_lane: {message}: DISPLAY\n'.encode(), 2)
        assert outputs[1] == (b'', f'run_lane: {message}: LANE_DISPLAY\n'.encode(), 2)
    else:
        stdout, stderr, rc = with_completion_check(outputs[0])
        stdout = b''.join(line.rstrip(b'\n') + b' --judge-model openai/gpt-4.1-mini\n'
                          if b'shared.functionchat.judge.run_judge ' in line else line
                          for line in stdout.splitlines(keepends=True))
        assert (stdout, stderr, rc) == outputs[1]
    assert outputs[1][2] == (2 if change in ('unknown', 'duplicate', 'prefix', 'empty', 'space') else 0)


def test_registry_explicit_taubench_prefix_trap(tmp_path):
    fx = RegistryComparison(tmp_path / 'checkout')
    fx.put('orchestration/models/sample.conf', SAMPLE + 'TAUBENCH_USER_MODEL=x\n')
    assert fx.lane('sample').returncode == 0
    fx.put('orchestration/tracks/taubench.sh', '# Only presence determines registration.\n')
    for result in (fx.cli('sample'), fx.lane('sample')):
        assert (result.returncode, result.stdout, result.stderr) == (2, b'', b'run_lane: unknown key: USER_MODEL\n')


def test_registry_longest_prefix_and_session_precedence(tmp_path):
    fx = RegistryComparison(tmp_path / 'checkout')
    for track in ('a', 'a_b', 'session'):
        fx.put('orchestration/tracks/' + track + '.sh', '# fixture\n')
    fx.put('orchestration/models/sample.conf', SAMPLE + 'SESSION_A_B=longest\nA_REPS=2\nA_B_REPS=1\n')
    values = assignments(fx.cli('sample', 'a_b'))
    assert values['SESSION'] == 'longest' and values['REPS'] == '1'
    assert values['SESSION_KMMLU'] == 'fixture'
