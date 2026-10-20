"""무엇: 공유 길이 경계 · 입력: 경계/미측정 · 출력: wrapper 계약 보존 · 계약 §4-3."""

import pytest
from jeveval.types.length_buckets import LENGTH_LIMITS
from jeveval.run.length import length_bucket as run_bucket
from jeveval.score.risk_mix import length_bucket


def test_constants_and_distinct_none_contracts():
    assert LENGTH_LIMITS == (4096, 8192, 16384)
    assert length_bucket(None) == 'unmeasured'
    with pytest.raises(ValueError): run_bucket(None)
    for limit in LENGTH_LIMITS:
        assert length_bucket(limit) == run_bucket(limit) == f'le_{limit}'
