"""무엇: 길이·결과 경계 통합 · 입력: 기존 길이 fixture/offsets · 출력: 분류·거부 · 계약 §4-3."""

from dataclasses import replace

import pytest

from jeveval.run.length import classify, length_bucket, token_end
from jeveval.run.outcome import call_record, final_record
from jeveval.run.plan_calls import plan_calls
from jeveval.types import LengthInfo


def test_boundaries_through_outcome(env, fixture_json, make_attempt, b1_raw):
    """fixture의 정상·초과·거부 우선·mismatch를 최종 레코드까지 검증한다."""
    source = fixture_json("length/boundaries.json")
    # B1 usage는 systemone의 추가 키 경고를 만들지 않아 fixture 경고 목록과 같다.
    plan, = plan_calls(env.item, env.task, env.bcfg, env.b1)
    for case in source["cases"]:
        value, expected = case["input"], case["expected"]
        length = LengthInfo(**{k: value[k] for k in ("length_tokens", "target_end", "limit", "fixed_tokens")})
        cut = classify(length)
        assert cut == ("target_cut" if case["name"] == "rejected_first"
                       else expected["reason"] or "not_truncated")
        raw = b1_raw([{"token": "A", "logprob": -.2}, {"token": "B", "logprob": -1}],
                     usage={"prompt_tokens": value["usage_input_tokens"]})
        rejected = value["matches_confirmed_input_limit_response"]
        attempt = make_attempt(plan, http_status=422 if rejected else 200,
                               response_raw="too long" if rejected else raw)
        call = call_record(plan, [attempt], length, env.bcfg, env.policy.max_attempts)
        final = final_record(plan.logical_id, [plan], [call])
        assert (final.status, final.reason, final.answered_over_limit, final.warnings) == (
            expected["status"], expected["reason"], expected["answered_over_limit"], expected["warnings"])
        assert (call.answers_parsed is not None) == value["validated_response"]


def test_b1_per_call_length_fixture(env, fixture_json, make_attempt, b1_raw):
    """같은 요청의 서로 다른 고정부가 다른 잘림을 만들고 최대 길이로 구간을 정한다."""
    source = fixture_json("length/boundaries.json")["b1_logical"]
    lengths = [LengthInfo.from_dict(v) for v in source["calls"]]
    item = replace(env.item, questions=[env.q, replace(env.q, id="other")])
    plans = plan_calls(item, env.task, env.bcfg, env.b1)
    raw = b1_raw([{"token": "A", "logprob": -1}, {"token": "B", "logprob": -1}])
    calls = [call_record(p, [make_attempt(p, response_raw=raw)], length, env.bcfg, env.policy.max_attempts)
             for p, length in zip(plans, lengths)]
    assert [c.reason for c in calls] == source["expected"]["classifications"]
    maximum = max(c.length.length_tokens for c in calls)
    assert maximum == source["expected"]["length_max"]
    assert length_bucket(maximum) == source["expected"]["bucket"]
    final = final_record(plans[0].logical_id, plans, calls)
    assert final.reason == "tail_cut" and final.answered_over_limit


@pytest.mark.parametrize("n,bucket", [(0, "le_4096"), (4096, "le_4096"), (4097, "le_8192"),
    (8192, "le_8192"), (8193, "le_16384"), (16384, "le_16384"), (16385, "gt_16384")])
def test_bucket_boundaries(n, bucket):
    """각 구간의 양끝을 검증한다."""
    assert length_bucket(n) == bucket


@pytest.mark.parametrize("end,expected", [(0, 0), (1, 1), (2, 1), (3, 2), (5, 3)])
def test_token_end(end, expected):
    """문자 끝이 토큰 내부·경계에 있을 때 끝 다음 토큰 번호를 확인한다."""
    assert token_end([(0, 2), (2, 3), (3, 5)], end) == expected


@pytest.mark.parametrize("end,expected", [(0, 0), (1, 3), (2, 6)])
def test_korean_byte_fragments(end, expected):
    """'한글'의 각 글자를 공유하는 UTF-8 세 조각 중 마지막 조각 다음을 반환한다."""
    assert token_end([(0, 1)] * 3 + [(1, 2)] * 3, end) == expected


@pytest.mark.parametrize("offsets,end,expected", [
    ([(0, 2), (1, 3)], 2, 2),
    ([(0, 3), (1, 2), (1, 2), (2, 3)], 2, 3),
    ([(0, 3), (1, 2)], 3, 1),
    ([(0, 1), (1, 1)], 1, 1), ([], 0, 0)])
def test_overlapping_offsets(offsets, end, expected):
    """끝 위치가 감소해도 start 순서가 맞으면 허용하고 마지막 덮는 토큰을 고른다."""
    assert token_end(offsets, end) == expected


@pytest.mark.parametrize("offsets,end", [([(1, 3), (0, 1)], 1),
    ([(0, 2), (1, 3), (0, 2)], 2),
    ([(0, 1), (2, 3)], 2), ([], 1), ([(0, 1)], 2), ([(-1, 1)], 0), ([(2, 1)], 0),
    ([(0, 1)], -1), ([(0, 1)], True)])
def test_invalid_offsets(offsets, end):
    """start 감소·미포함·음수·뒤집힌 범위 입력을 조용히 잘못 측정하지 않는다."""
    with pytest.raises(ValueError):
        token_end(offsets, end)


@pytest.mark.parametrize("code,raw", [(200, "{}"), (422, "too long"), (503, "{}"), (500, "{}")])
def test_length_required_on_every_sent_response(env, make_attempt, code, raw):
    """검증 실패·거부·HTTP 오류도 length=None이면 기록할 수 없다."""
    with pytest.raises(ValueError, match="length"):
        call_record(env.plan, [make_attempt(env.plan, http_status=code, response_raw=raw)], None, env.cfg, env.policy.max_attempts)
