"""무엇: 메모리 요청 결과 왕복 · 입력: 합성 관측 · 출력: 검증 · 계약 §7-8·§8-5."""

from dataclasses import replace

from jeveval.types import RequestOutcome
from samples import outcome


def test_valid_missing_and_invalid_outcomes():
    for original in (outcome(), replace(outcome(),gold={'ready':None},mask_empty=True,wrong=None),
                     replace(outcome(),status='error',valid=False,s=None,wrong=None,answer=None,length_max=None)):
        data = original.to_dict()
        restored = RequestOutcome.from_dict(data)
        data['gold']['ready'] = 'false'
        assert restored == original
