"""무엇: 재시도 정책 스키마 · 입력: 메모리 설정 · 출력: RetryPolicy/전체 오류 · 계약 §4-2·§8-1."""

import pytest

from jeveval.contract.policy import validate_retry_policy
from jeveval.types import RetryPolicy

KEY_ERROR = "retry requires exactly max_attempts, http_statuses, backoff_seconds"
BUDGET_ERROR = "max_attempts must be a positive integer"
STATUS_ERROR = "http_statuses must be unique HTTP status integers"
WAIT_ERROR = "backoff_seconds must list one nonnegative wait per non-final attempt"


def policy_data(**changes):
    return {"retry": {"max_attempts": 3, "http_statuses": [503, 529],
                      "backoff_seconds": [1, 2], **changes}}


@pytest.mark.parametrize("expected", [RetryPolicy(3, [503, 529], [0, .5]),
                                      RetryPolicy(1, [100, 599], [])])
def test_valid_policy_returns_retry_policy(expected):
    result = validate_retry_policy({"retry": expected.to_dict()})
    assert isinstance(result, RetryPolicy) and result == expected
    assert RetryPolicy.from_dict(result.to_dict()) == result


@pytest.mark.parametrize("data", [None, [], "retry", {}, {"retry": []}, {"retry": None},
    {"retry": {}, "extra": 1}])
def test_policy_requires_single_retry_mapping(data):
    assert validate_retry_policy(data) == ["policy requires exactly one mapping: retry"]


@pytest.mark.parametrize("key", ["max_attempts", "http_statuses", "backoff_seconds", "extra"])
def test_retry_keys_are_closed(key):
    data = policy_data()
    if key == "extra":
        data["retry"][key] = 1
    else:
        del data["retry"][key]
    assert validate_retry_policy(data) == [KEY_ERROR]


@pytest.mark.parametrize("value", [None, True, False, 0, -1, 3.0, "3"])
def test_invalid_budget_returns_error(value):
    assert validate_retry_policy(policy_data(max_attempts=value)) == [BUDGET_ERROR]


@pytest.mark.parametrize("value", [None, (), "503", [], [503, 503], [True], [503.0],
                                   ["503"], [99], [600], [[]], [{}]])
def test_invalid_statuses_return_errors_without_raising(value):
    assert validate_retry_policy(policy_data(http_statuses=value)) == [STATUS_ERROR]


@pytest.mark.parametrize("value", [None, (1, 2), "1,2", [], [1], [1, 2, 3], [True, 2],
    [-1, 2], ["1", 2], [None, 2], [float("nan"), 2], [float("inf"), 2], [-float("inf"), 2]])
def test_invalid_backoff_returns_error(value):
    assert validate_retry_policy(policy_data(backoff_seconds=value)) == [WAIT_ERROR]


def test_independent_policy_errors_are_collected():
    data = policy_data(max_attempts=0, http_statuses=[True], backoff_seconds=[-1])
    assert validate_retry_policy(data) == [BUDGET_ERROR, STATUS_ERROR, WAIT_ERROR]
