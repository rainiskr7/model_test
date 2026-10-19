"""CD3/CH1: retain pre-v8 015c3c5 evidence independently of the older oracles."""
import json

import pytest

from orchestration.tests.laneconf_support import REPO, SAMPLE
from orchestration.tests.registry_support import RegistryComparison


class V8Comparison(RegistryComparison):
    revision = '015c3c5f5fa7318a03a58d5d0456f8178ca26d04'


LANES = [(model, 'kmmlu') for model in ('qwen38', 'qwenfp8', 'qwen35fp8', 'qwen36')] + [('qwen35fp8', 'full')]


@pytest.mark.parametrize('model,track', LANES)
def test_cd3_five_lane_bytes_match_pre_v8(tmp_path, model, track):
    fx = V8Comparison(tmp_path / 'checkout')
    fx.put(f'orchestration/models/{model}.conf', (REPO / f'orchestration/models/{model}.conf').read_text())
    (fx.base / '.env').unlink()
    outputs = []
    for side in ('HEAD', 'working'):
        fx.install(side)
        result = fx.lane(model, track)
        fx.evidence('CD3/' + side, result)
        assert result.returncode == 0, result.stderr
        outputs.append((result.stdout, result.stderr, result.returncode))
        fx.assert_dry()
    assert outputs[0] == outputs[1]
    print(f'CD3 {model}/{track}: identical stdout/stderr/rc; {fx.base}/evidence')


def test_ch1_pre_v8_missing_run_false_success_then_rejected(tmp_path):
    fx = V8Comparison(tmp_path / 'checkout')
    fx.put('orchestration/models/sample.conf', SAMPLE + 'SESSION_DEMO=fixture\n')
    fx.put('orchestration/tracks/demo.sh', 'track_dry_run() { printf "demo\\n"; }\n')
    (fx.orch / 'lanes/demo.sh').symlink_to('../run_lane.sh')
    observations = {}
    for side in ('HEAD', 'working'):
        fx.install(side)
        result = fx.lane('sample', 'demo')
        fx.evidence('CH1/' + side, result)
        observations[side] = dict(rc=result.returncode, rejects_missing=result.returncode == 2)
        if side == 'HEAD':
            assert result.returncode == 0 and result.stdout.endswith(b'demo\n')
        else:
            assert (result.returncode, result.stdout, result.stderr) == (
                2, b'', b'run_lane: track demo defines no track_run\n')
    fx.put('evidence/CH1/verdicts.json', json.dumps(observations, indent=2))
    print(f'CH1 HEAD FAIL -> working PASS: {fx.base}/evidence')
