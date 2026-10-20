"""무엇: 보조 집계 계약 · 입력: 합성 집계/변조 · 출력: 정확한 거부 · 계약 §7-4c."""

from copy import deepcopy
import pytest
from jeveval.score.selective_artifact import build, validate
from tests.score.test_risk import row


def fixture():
    identity = dict(model='m', set='s', variant='v', run_id='r')
    hashes = {'risk.json': 'a'*64, 'test/final.jsonl': 'b'*64}
    risk = dict(cells={t: dict(test=dict(n_denom=1, n_accepted=1)) for t in ("0.01", "0.02", "0.05")})
    value = build([row(0, "test")], identity, hashes, risk)
    return value, identity, hashes, risk


def test_validation_and_public_projection():
    args = fixture()
    validate(*args)
    assert 'logical_id' not in str(args[0]) and 'grid' in args[0]


@pytest.mark.parametrize('attack', ['identity', 'digest', 'count', 'range', 'grid', 'endpoint'])
def test_invalid_auxiliary_rejected(attack):
    value, identity, hashes, risk = deepcopy(fixture())
    if attack == 'identity': value['run_id'] = 'other'
    if attack == 'digest': value['inputs']['risk.json'] = 'c'*64
    if attack == 'count': value['n_denom'] = 3
    if attack == 'range': value['auroc'] = float('nan')
    if attack == 'grid': value['grid'][0]['coverage'] = .5
    if attack == 'endpoint': value['grid'][-1].update(n_accepted=0, k_errors=0, coverage=0., risk=None)
    with pytest.raises(ValueError): validate(value, identity, hashes, risk)


@pytest.mark.parametrize('field', ['target', 'coverage', 'risk'])
def test_boolean_is_not_a_probability(field):
    value, identity, hashes, risk = fixture()
    value['grid'][-1][field] = True
    with pytest.raises(ValueError): validate(value, identity, hashes, risk)
