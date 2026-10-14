"""무엇: T0 길이 경계 통합 · 입력: 전체/질문별 길이·HTTP·usage · 출력: 경계 전용 판정 · 계약 T-g."""

from dataclasses import replace
import json

import pytest

from jeveval.t0.boundary import judge_boundary
from jeveval.t0.judge import judge
from jeveval.types.t0 import T0Boundary


@pytest.mark.parametrize("lengths,overflow,http,length_status,body,expected", [
    ([100], "reject", 200, "ok", "", "PASS"),
    ([100], "reject", 200, "truncated", "", "FAIL"),
    ([100], "reject", 422, "rejected", "limit", "FAIL"),
    ([101], "reject", 422, "rejected", "input limit 100", "PASS"),
    ([80,101], "reject", 422, "rejected", "input limit 100", "PASS"),
    ([101], "reject", 422, "rejected", "schema error", "FAIL"),
    ([101], "reject", 400, "rejected", "input limit 100", "FAIL"),
    ([101], "truncate_tail", 200, "truncated", "", "PASS"),
    ([101], "truncate_tail", 200, "ok", "", "FAIL"),
    ([101], "truncate_tail", 503, "truncated", "", "INCOMPLETE"),
    (None, "truncate_tail", 200, "ok", "", "INCOMPLETE"),
])
def test_boundary_policy(scenario, lengths, overflow, http, length_status, body, expected):
    _, obs, _ = scenario
    boundary = T0Boundary(lengths, 100, overflow, {"status":422,"body_regex":r"input limit \d+"})
    observation = replace(obs, http_status=http, response_raw=body, length_status=length_status)
    assert judge_boundary(boundary, observation) == expected


@pytest.mark.parametrize("usage", [None, 0, 100, 1700, True])
def test_usage_never_controls_boundary_and_reference_is_not_compared(scenario, usage):
    case, obs, _ = scenario
    body = json.loads(obs.response_raw)
    body["usage"] = {"input_tokens":usage}
    observation = replace(obs, response_raw=json.dumps(body), length_status="truncated")
    case = replace(case, boundary=T0Boundary([101], 100, "truncate_tail"))
    result = judge([case], [], [observation], {}, inputs_sha256="a" * 64,
                   reference_epsilon=5e-5, server_epsilon=5e-5)
    assert result.status == "PASS" and result.n_compared == 0 and result.max_abs_diff is None


def test_expected_rejection_succeeds_and_invalid_200_fails(scenario):
    case, obs, _ = scenario
    case = replace(case, boundary=T0Boundary([101], 100, "reject", {"status":400,"body_regex":"maximum"}))
    obs = replace(obs, http_status=400, response_raw="maximum context", length_status="rejected")
    kwargs = dict(inputs_sha256="a" * 64, reference_epsilon=5e-5, server_epsilon=5e-5)
    assert judge([case], [], [obs], {}, **kwargs).status == "PASS"
    case = replace(case, boundary=T0Boundary([100], 100, "reject"))
    obs = replace(obs, http_status=200, response_raw="invalid", length_status="ok")
    assert judge([case], [], [obs], {}, **kwargs).status == "FAIL"
