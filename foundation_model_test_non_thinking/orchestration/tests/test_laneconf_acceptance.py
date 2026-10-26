"""CA1/CA2/CA3 use copied code, synthetic secrets, real loader, and byte evidence."""
import json

import pytest

from orchestration.tests.laneconf_support import (
    BASELINE_REVISION, Comparison, REPO, SAMPLE, assignments, host_line,
)
from orchestration.tests.registry_support import with_completion_check

MODELS = ['qwen38', 'qwenfp8', 'qwen35fp8', 'qwen36']
LANES = [(model, 'kmmlu') for model in MODELS] + [('qwen35fp8', 'full')]


def test_ca1_original_mismatch_then_both_reject(tmp_path):
    fx = Comparison(tmp_path / 'checkout')
    fx.put('orchestration/models/sample.conf', SAMPLE + 'HOST_DEFAULT=second\n')
    fx.install('HEAD')
    old_lane, old_smoke = fx.lane('sample'), fx.context('sample')
    fx.evidence('CA1/HEAD/lane', old_lane)
    fx.evidence('CA1/HEAD/smoke', old_smoke)
    assert old_smoke.returncode == 0, old_smoke.stderr
    assert host_line(old_lane) == 'second'
    assert json.loads(old_smoke.stdout)['host'] == 'first'
    fx.install('working')
    new_lane = fx.lane('sample')
    new_smoke = fx.python('-m', 'orchestration.smoke.main', 'sample', 'harness')
    fx.evidence('CA1/working/lane', new_lane)
    fx.evidence('CA1/working/smoke', new_smoke)
    assert new_lane.returncode == new_smoke.returncode == 2
    assert new_lane.stdout == new_smoke.stdout == b''
    assert new_lane.stderr == b'run_lane: duplicate key: HOST_DEFAULT\n'
    assert new_smoke.stderr == b'smoke: duplicate key: HOST_DEFAULT\n'
    fx.assert_dry()
    print(f'CA1 HEAD={BASELINE_REVISION}: lane=second smoke=first -> both rc=2; {fx.base}/evidence')


@pytest.mark.parametrize('model,track', LANES)
@pytest.mark.parametrize('override', [None, '', 'fixture.invalid:18023'])
def test_ca2_real_models_lane_loader_smoke(tmp_path, model, track, override):
    fx = Comparison(tmp_path / 'checkout')
    fx.put(f'orchestration/models/{model}.conf', (REPO / f'orchestration/models/{model}.conf').read_text())
    resolved = assignments(fx.cli(model, track))
    extra = {} if override is None else {resolved['HOST_ENV']: override}
    lane = fx.lane(model, track, extra)
    fx.evidence('CA2/lane', lane)
    expected_host = override or resolved['HOST_DEFAULT']
    assert host_line(lane) == expected_host  # (가): CLI HOST_ENV/HOST_DEFAULT semantics.
    assert (fx.base / 'loader_inputs').read_text().splitlines() == [resolved['CONFIG']]  # (나)
    kmmlu = assignments(fx.cli(model, 'kmmlu'))
    smoke = fx.context(model, extra)
    fx.evidence('CA2/smoke', smoke)
    assert smoke.returncode == 0, smoke.stderr
    assert json.loads(smoke.stdout) == dict(host=expected_host, config=kmmlu['CONFIG'],
                                           keyvar=kmmlu['KEYVAR'], tokenizer=kmmlu['LANE_TOKENIZER'])  # (다)
    fx.assert_dry()


@pytest.mark.parametrize('settings,reps,tokenizer', [
    ('', '3', 'unused'),
    ('REPS=2\nKMMLU_REPS=1\n', '1', 'unused'),
    ('KMMLU_REPS=1\nREPS=2\n', '1', 'unused'),
    ('KMMLU_LANE_TOKENIZER="a b=c"\n', '3', 'a b=c'),
    ("KMMLU_LANE_TOKENIZER='$(touch unexpected)'\n", '3', '$(touch unexpected)'),
])
def test_ca2_synthetic_scope_quotes_defaults(tmp_path, settings, reps, tokenizer):
    fx = Comparison(tmp_path / 'checkout')
    fx.put('orchestration/models/sample.conf', SAMPLE + settings)
    resolved = assignments(fx.cli('sample'))
    lane, smoke = fx.lane('sample'), fx.context('sample')
    assert resolved['REPS'] == reps
    assert lane.stdout.count(b'SESSION=') == int(reps)
    assert host_line(lane) == resolved['HOST_DEFAULT']
    assert (fx.base / 'loader_inputs').read_text() == resolved['CONFIG'] + '\n'
    assert smoke.returncode == 0, smoke.stderr
    assert json.loads(smoke.stdout) == dict(host='first', config=resolved['CONFIG'],
                                           keyvar=resolved['KEYVAR'], tokenizer=tokenizer)
    assert resolved['LANE_TOKENIZER'] == tokenizer
    assert not (fx.base / 'unexpected').exists()
    fx.assert_dry()


@pytest.mark.parametrize('model,track', LANES)
def test_ca3_same_path_head_bytes(tmp_path, model, track):
    fx = Comparison(tmp_path / 'checkout')
    fx.put(f'orchestration/models/{model}.conf', (REPO / f'orchestration/models/{model}.conf').read_text())
    (fx.base / '.env').unlink()  # Both dry runs must succeed without credentials.
    results = []
    for side in ('HEAD', 'working'):
        fx.install(side)
        result = fx.lane(model, track)
        fx.evidence('CA3/' + side, result)
        assert result.returncode == 0, result.stderr
        results.append((result.stdout, result.stderr, result.returncode))
        fx.assert_dry()
    stdout, stderr, rc = with_completion_check(results[0])
    stdout = b''.join(line.rstrip(b'\n') + b' --judge-model openai/gpt-4.1-mini\n'
                      if b'shared.functionchat.judge.run_judge ' in line else line
                      for line in stdout.splitlines(keepends=True))
    assert (stdout, stderr, rc) == results[1]
    print(f'CA3 {model}/{track}: identical except C7 follow-up; {fx.base}/evidence')
