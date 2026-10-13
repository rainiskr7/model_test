"""무엇: 누적 재시도 정책 · 입력: 시도/기존 resume fixture · 출력: 대기·소진 복구 · 계약 §4-2·§8-6 B."""

from dataclasses import replace

import pytest

from jeveval.run.outcome import call_record
from jeveval.run.policy import MAX_ATTEMPTS, decide
from jeveval.types import AttemptRecord, AttemptResult


@pytest.mark.parametrize("attempt,wait", [(1, 1), (2, 2), (3, 4), (4, 8), (5, None)])
@pytest.mark.parametrize("code", [503, 529])
def test_backoff_and_exhaustion(env, make_attempt, attempt, wait, code):
    """마지막에는 재시도도 대기도 없고 이전 시도에는 지수 대기를 쓴다."""
    result = decide(make_attempt(env.plan, http_status=code), attempt)
    assert result.terminal == (wait is None) and result.wait_s == wait


@pytest.mark.parametrize("value,wait", [("3", 3), ("0", 0), ("003", 3), (3, 3), (3.0, 3),
    ("abc", 2), ("-1", 2), ("1.5", 2), (1.5, 2), (-1, 2), (True, 2),
    (" 3", 2), ("+3", 2), ("Wed, 21 Oct 2015 07:28:00 GMT", 2), (float("inf"), 2)])
def test_retry_after(env, make_attempt, value, wait):
    """초 정수만 받아들이고 잘못된 머리글·기존 숫자 기록에는 기본 대기를 쓴다."""
    result = decide(make_attempt(env.plan, http_status=503, retry_after=value), 2)
    assert not result.terminal and result.wait_s == wait


@pytest.mark.parametrize("code", [200, 201, 103, 301, 422, 400, 500])
def test_nonretry_statuses(env, make_attempt, code):
    """200 검증 여부와 무관하게 지정 코드 이외는 재시도하지 않는다."""
    decision = decide(make_attempt(env.plan, http_status=code), 1)
    assert decision.terminal and decision.wait_s is None


@pytest.mark.parametrize("code", [200, 422, None])
@pytest.mark.parametrize("error", ["timeout", "transport:IncompleteRead"])
def test_transport_precedes_status(code, error):
    """client의 AttemptResult도 HTTP 코드보다 전송 실패를 우선한다."""
    result = AttemptResult("start", "end", 1, code, "3", error, "partial")
    decision = decide(result, 1)
    assert not decision.terminal and decision.wait_s == 3


@pytest.mark.parametrize("number,maximum", [(0, 5), (6, 5), (1, 0), (True, 5), (1, False)])
def test_invalid_budget(env, make_attempt, number, maximum):
    """시도 번호와 상한의 잘못된 범위를 거부한다."""
    with pytest.raises(ValueError):
        decide(make_attempt(env.plan), number, maximum)


def test_resume_fixture_budget(env, fixture_json):
    """기존 기록의 호출별 terminal·다음 번호·남은 예산을 실제 정책으로 계산한다."""
    source = fixture_json("resume/retry_budget.json")
    assert source["max_attempts"] == MAX_ATTEMPTS
    for case in source["cases"]:
        groups = {}
        for value in case["attempts"]:
            record = AttemptRecord.from_dict(value)
            groups.setdefault(record.call_id, []).append(record)
        pending, done = [], []
        for call_id, attempts in groups.items():
            last = attempts[-1]
            decision = decide(last, last.attempt)
            (done if decision.terminal else pending).append(call_id)
            if not decision.terminal:
                assert len(attempts) + 1 == case["expected"]["next_attempt"]
                assert MAX_ATTEMPTS - len(attempts) == case["expected"]["remaining_attempts"]
            elif len(attempts) == MAX_ATTEMPTS:
                plan = replace(env.plan, call_id=call_id, logical_id=last.logical_id,
                               request_sha256=last.request_sha256)
                final = call_record(plan, attempts, env.length, env.cfg)
                assert (final.status, final.reason) == (case["expected"]["status"], case["expected"]["reason"])
                attempts[-1] = replace(last, terminal=False)
                assert call_record(plan, attempts, env.length, env.cfg) == final
                assert case["expected"]["new_calls"] == case["expected"]["remaining_attempts"] == 0
        if "recover_call_ids" in case["expected"]:
            assert done == case["expected"]["recover_call_ids"]
            assert pending == case["expected"]["retry_call_ids"]


def test_shared_custom_budget(env, make_attempt):
    """정책과 결과 변환에 같은 상한을 전달해 non-terminal 소진을 복구한다."""
    attempts = [make_attempt(env.plan, attempt=i, http_status=503, terminal=False) for i in (1, 2)]
    assert decide(attempts[-1], 2, max_attempts=2).terminal
    assert call_record(env.plan, attempts, env.length, env.cfg, max_attempts=2).reason == "http_503"
    with pytest.raises(ValueError, match="not complete"):
        call_record(env.plan, attempts, env.length, env.cfg)
