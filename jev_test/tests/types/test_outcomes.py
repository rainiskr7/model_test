"""무엇: 메모리 요청 결과 왕복 · 입력: 합성 관측 · 출력: 검증 · 계약 §7-8·§8-5."""

from dataclasses import replace

import pytest

from jeveval.types import RequestOutcome
from samples import outcome


def test_valid_missing_and_invalid_outcomes():
    for original in (outcome(), replace(outcome(),gold={'ready':None},mask_empty=True,wrong=None),
                     replace(outcome(),status='error',valid=False,s=None,wrong=None,answer=None,length_max=None)):
        data = original.to_dict()
        restored = RequestOutcome.from_dict(data)
        data['gold']['ready'] = 'false'
        data['roles']['ready'] = 'diagnostic'
        assert restored == original


@pytest.mark.parametrize('roles', [{}, {'other': 'success'}, {'ready': 'invalid'}])
def test_roles_require_all_question_ids_and_known_roles(roles):
    with pytest.raises(ValueError):
        replace(outcome(), roles=roles)


def test_roles_are_required_and_diagnostic_roundtrips():
    data = outcome().to_dict()
    del data['roles']
    with pytest.raises(TypeError):
        RequestOutcome.from_dict(data)
    value = replace(outcome(), roles={'ready': 'diagnostic'})
    assert RequestOutcome.from_dict(value.to_dict()) == value
