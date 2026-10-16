"""출력 경로별 반올림 정책 파싱."""

import pytest

from jeveval.t0.rounding import parse, epsilon


@pytest.mark.parametrize("policy", ["reference=-1", "reference=17", "other=4", "reference=4,reference=4",
                                   "server=True", "server=４"])
def test_rounding_invalid(policy):
    with pytest.raises(ValueError):
        parse(policy)



@pytest.mark.parametrize("policy,expected", [(None, {"reference": None, "server": None}),
    ("", {"reference": None, "server": None}), ("server=0", {"reference": None, "server": 0}),
    ("server=16,reference=4", {"reference": 4, "server": 16})])
def test_rounding_paths_and_endpoints(policy, expected):
    assert parse(policy) == expected


@pytest.mark.parametrize("digits,expected", [(None, None), (0, .5), (4, .00005), (16, 5e-17)])
def test_epsilon_is_half_rounding_unit(digits, expected):
    assert epsilon(digits) == expected
