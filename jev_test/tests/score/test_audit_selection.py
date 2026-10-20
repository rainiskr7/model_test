"""무엇: 감사 적격 선택 · 입력: 사전/사후 합성 증거 · 출력: 정확 tuple 연결 · 계약 §7-6."""

from copy import deepcopy
import pytest
from jeveval.score.audit_selection import select_audit_evidence, RULES


def evidence(retrospective=False):
    fp = dict(model='m', set='kosgd2', variant='full', run_id='r', inputs=dict(task_path='configs/tasks/a.yaml'),
              files={'configs/tasks/a.yaml': 'a'*64, 'configs/splits/kosgd2.json': 'b'*64, 'configs/tasks/b1.yaml': 'c'*64})
    value = dict(schema='audit_v4/1', set='kosgd2', profile='kosgd2', retrospective=retrospective,
        inputs=dict(files=deepcopy(fp['files'])), code=dict(audit_sha256='d'*64),
        models=dict(m=dict(variants=dict(full=dict(measurement_config=False)))),
        per_variant=dict(full={r: dict(status='PASS') for r in RULES}), historical_calls=None)
    if retrospective:
        value['historical_calls'] = dict(runs=[dict(model='m', variant='full', run_id='r', status='PASS')])
    return value, fp


def test_prospective_and_legacy_retrospective_set_inheritance():
    for retrospective in (False, True):
        assert select_audit_evidence(*evidence(retrospective))[2]


@pytest.mark.parametrize('field,value', [('model', 'other'), ('run_id', 'other'), ('variant', 'actions_only'),
    ('set', 'kosgd'), ('status', 'FAIL'), ('status', 'INCOMPLETE')])
def test_retrospective_mismatch_never_links(field, value):
    audit, fp = evidence(True)
    audit['historical_calls']['runs'][0][field] = value
    assert not select_audit_evidence(audit, fp)[2]


@pytest.mark.parametrize('field', ['set', 'profile'])
def test_kosgd_prefix_does_not_match_kosgd2(field):
    audit, fp = evidence()
    audit[field] = 'kosgd'
    with pytest.raises(ValueError): select_audit_evidence(audit, fp)


def test_failed_rule_is_kept_after_eligible_link():
    audit, fp = evidence()
    audit['per_variant']['full']['R4']['status'] = 'FAIL'
    rules, _, linked = select_audit_evidence(audit, fp)
    assert linked and rules['R4']['status'] == 'FAIL'
