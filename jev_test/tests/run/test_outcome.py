"""무엇: 결과 변환·복구 통합 · 입력: 기존 응답/B1/기록 fixture · 출력: Call/FinalRecord · 계약 §3–5."""

from dataclasses import replace
import json
from pathlib import Path

import pytest

from jeveval.run.outcome import call_record, final_record
from jeveval.run.plan_calls import plan_calls
from jeveval.types import AttemptRecord, CallRecord, Request


@pytest.mark.parametrize("configured,code,raw,reason", [
    (400, 400, "This model's maximum context length is 65536 tokens. ...", "input_limit"),
    (400, 400, "max allowed: 20", "http_400"),
    (422, 400, "maximum context length is 65536", "http_400"),
    (400, 422, "maximum context length is 65536", "http_422_other"),
    (422, 422, "maximum context length is 65536", "input_limit"),
])
def test_b1_model_specific_length_rejection(env, make_attempt, configured, code, raw, reason):
    cfg = replace(env.bcfg, input_limit_response={
        "status": configured, "body_regex": "maximum context length is"})
    plan, = plan_calls(env.item, env.task, cfg, env.b1)
    call = call_record(plan, [make_attempt(plan, http_status=code, response_raw=raw)], env.length, cfg, env.policy.max_attempts)
    assert call.reason == reason
    assert call.status == ("rejected" if reason == "input_limit" else "error")


@pytest.mark.parametrize("path", sorted((Path(__file__).parents[1] / "fixtures/responses").glob("*.json")),
                         ids=lambda p: p.stem)
def test_response_fixtures(env, make_attempt, path):
    """모든 기존 응답 fixture를 결과 변환에 통과시켜 사유·경고·전체 맵 규칙을 검증한다."""
    source = json.loads(path.read_text())
    questions, expected = source["request_questions"], source["expected"]
    plan = replace(env.plan, request=Request("model", "원문", questions), question_ids=list(questions),
                   question_types={key: q["type"] for key, q in questions.items()})
    result = call_record(plan, [make_attempt(plan, response_raw=source["response_raw"])], env.length, env.cfg, env.policy.max_attempts)
    assert result.reason == expected["reason"] and result.warnings == expected["warnings"]
    assert result.status == ("ok" if expected["valid"] else "error")
    assert (result.answers_parsed is not None) == expected["valid"]
    if expected["valid"]:
        assert set(result.answers_parsed) == set(questions)


def test_terminal_recovery_exact_final(env, fixture_json):
    """이미 저장된 terminal 시도에서 fixture와 정확히 같은 final을 복구한다."""
    source = fixture_json("resume/terminal_recovery.json")
    attempts = [AttemptRecord.from_dict(json.loads(line)) for line in source["attempts_jsonl"].splitlines()]
    plan = replace(env.plan, request_sha256=attempts[0].request_sha256)
    call = call_record(plan, attempts, type(env.length).from_dict(source["input_length"]), env.cfg, env.policy.max_attempts)
    assert final_record(plan.logical_id, [plan], [call]).to_dict() == source["expected"]["final"]


def test_b1_renormalization_and_missing_fixtures(env, fixture_json, make_attempt, b1_raw):
    """라벨 교환·동률·누락·-inf를 실제 B1 봉투에서 파싱하고 저장 가능성을 확인한다."""
    plan, = plan_calls(env.item, env.task, env.bcfg, env.b1)
    for case in fixture_json("b1/renormalization.json")["cases"]:
        changed = replace(plan, b1_call=replace(plan.b1_call, label_order=case["label_order"], label_map=case["label_map"]))
        result = call_record(changed, [make_attempt(changed, response_raw=b1_raw(case["top_logprobs"]))], env.length, env.bcfg, env.policy.max_attempts)
        parsed, expected = result.answers_parsed[env.q.id], case["expected"]["parsed"]
        assert result.status == "ok" and parsed.answer == expected["answer"]
        assert parsed.probs == pytest.approx(expected["probs"])
        assert parsed.confidence == pytest.approx(expected["confidence"])
        assert result.label_map == case["label_map"]
    source = fixture_json("b1/missing_label.json")
    for case in source["cases"]:
        rows = case.get("top_logprobs") or json.loads(case["top_logprobs_raw"])
        result = call_record(plan, [make_attempt(plan, response_raw=b1_raw(rows))], env.length, env.bcfg, env.policy.max_attempts)
        assert (result.status, result.reason) == (source["expected"]["status"], source["expected"]["reason"])
        assert result.answers_parsed is None and result.label_map == source["label_map"]
        assert CallRecord.from_dict(result.to_dict()) == result
        if case["name"] == "nonfinite":
            assert result.top_logprobs_raw[1]["logprob"] == "-inf"


@pytest.mark.parametrize("kind", ["systemone", "b1"])
@pytest.mark.parametrize("code,raw,error,expected", [
    (200, "{}", "timeout", "timeout"), (422, "too long", "transport:IncompleteRead", "transport"),
    (200, {"b64": "/w=="}, None, "bad_body"), (200, "{}", None, "bad_body"),
    (422, "too long", None, "input_limit"), (422, "other", None, "http_422_other"),
    (422, {"b64": "dG9vIGxvbmc="}, None, "http_422_other"),
    *[(code, "{}", None, f"http_{code}") for code in (103, 201, 301, 400, 500, 503, 529)]])
def test_response_branches(env, make_attempt, kind, code, raw, error, expected):
    """두 경로의 전송·코드·본문 실패와 거부 우선순위를 검증한다."""
    cfg = env.cfg if kind == "systemone" else env.bcfg
    plan, = plan_calls(env.item, env.task, cfg, env.b1)
    result = call_record(plan, [make_attempt(plan, http_status=code, response_raw=raw, transport_error=error)], env.length, cfg, env.policy.max_attempts)
    assert result.reason == expected and result.status == ("rejected" if expected == "input_limit" else "error")
    assert result.answers_parsed is None and result.length == env.length
    assert result.label_map == (plan.b1_call.label_map if kind == "b1" else None)
    if code == 422:
        no_pattern = call_record(plan, [make_attempt(plan, http_status=422, response_raw=raw)], env.length,
                                 replace(cfg, input_limit_response=None), env.policy.max_attempts)
        assert no_pattern.reason == "http_422_other"


@pytest.mark.parametrize("kind,key", [("systemone", "input_tokens"), ("b1", "prompt_tokens")])
@pytest.mark.parametrize("code", [200, 422, 503])
@pytest.mark.parametrize("value", [12, True])
def test_usage_independent_of_answer_and_http(env, make_attempt, kind, key, code, value):
    """오류 본문의 정수 usage는 보존하고 bool은 경고와 함께 누락으로 둔다."""
    cfg = env.cfg if kind == "systemone" else env.bcfg
    plan, = plan_calls(env.item, env.task, cfg, env.b1)
    raw = json.dumps({"usage": {key: value}, "error": "too long"})
    result = call_record(plan, [make_attempt(plan, http_status=code, response_raw=raw)], env.length, cfg, env.policy.max_attempts)
    assert result.usage == ({"input_tokens": 12} if type(value) is int else None)
    assert ("usage_input_tokens_invalid" in result.warnings) == (type(value) is bool)


@pytest.mark.parametrize("failure", ["empty", "overflow", "gap", "id", "hash", "logical", "early_terminal"])
def test_attempt_integrity(env, make_attempt, failure):
    """기록 예산·번호·계획 연결 위반을 결과로 채택하지 않는다."""
    attempts = [make_attempt(env.plan)]
    if failure == "empty":
        attempts = []
    elif failure == "overflow":
        attempts = [make_attempt(env.plan, attempt=i, terminal=False) for i in range(1, 7)]
    elif failure == "early_terminal":
        attempts.append(make_attempt(env.plan, attempt=2))
    else:
        key, value = {"gap": ("attempt", 2), "id": ("call_id", "wrong"),
                      "hash": ("request_sha256", "wrong"), "logical": ("logical_id", "wrong")}[failure]
        attempts[0] = replace(attempts[0], **{key: value})
    with pytest.raises(ValueError):
        call_record(env.plan, attempts, env.length, env.cfg, env.policy.max_attempts)


def test_partial_record_fixture_and_final_precedence(env, fixture_json):
    """B1 부분 실패 모양을 정확히 재현하고 순서·최악 상태·관측 플래그를 검증한다."""
    source = next(c["record"] for c in fixture_json("records/roundtrip.json")["cases"] if c["name"] == "b1_partial")
    calls = [CallRecord.from_dict(c) for c in source["calls"]]
    plans = [replace(env.plan, call_id=c.call_id, logical_id=source["logical_id"]) for c in calls]
    assert final_record(source["logical_id"], plans, calls).to_dict() == source
    calls[0] = replace(calls[0], status="truncated", reason="tail_cut", warnings=["first", "shared"])
    calls[1] = replace(calls[1], warnings=["shared", "last"])
    result = final_record(source["logical_id"], plans, calls)
    assert result.reason == "b1_missing_label" and result.answered_over_limit
    assert result.warnings == ["first", "shared", "last"]
    calls[1] = replace(calls[1], status="rejected", reason="input_limit")
    assert final_record(source["logical_id"], plans, calls).reason == "input_limit"
    calls[0] = replace(calls[0], status="error", reason="timeout", answers_parsed=None)
    calls[1] = replace(calls[1], status="error", reason="transport")
    assert final_record(source["logical_id"], plans, calls).reason == "timeout"
    with pytest.raises(ValueError):
        final_record(source["logical_id"], plans, calls[::-1])


def test_systemone_warning_order_and_unmodified_probabilities(env, make_attempt):
    """검증·usage·파싱 경고가 중복 없이 순서를 유지하고 원 확률은 바뀌지 않는다."""
    questions = {"pick": {"type": "choice", "criteria": {"a": "A", "b": "B"}}}
    plan = replace(env.plan, request=Request("model", "state", questions),
                   question_ids=["pick"], question_types={"pick": "choice"})
    answer = {"type": "choice", "choice": "b", "confidence": .2, "probabilities": {"a": .8, "b": .2}}
    raw = json.dumps({"answers": {"pick": answer}, "usage": {"input_tokens": True}})
    result = call_record(plan, [make_attempt(plan, response_raw=raw)], env.length, env.cfg, env.policy.max_attempts)
    assert result.warnings == ["extra_keys", "usage_input_tokens_invalid", "choice_not_argmax"]
    assert result.status == "ok" and result.answers_parsed["pick"].probs == answer["probabilities"]


def test_b1_warning_order_and_transport_usage(env, make_attempt, b1_raw):
    """usage 경고 다음 토큰 경고 순서를 보존하고 전송 실패에서도 usage를 추출한다."""
    plan, = plan_calls(env.item, env.task, env.bcfg, env.b1)
    rows = [{"token": "X", "logprob": -1}, {"token": "A", "logprob": -2},
            {"token": " A ", "logprob": -1}, {"token": "B", "logprob": -1}]
    raw = b1_raw(rows, usage={"prompt_tokens": True})
    result = call_record(plan, [make_attempt(plan, response_raw=raw)], env.length, env.bcfg, env.policy.max_attempts)
    assert result.warnings == ["usage_input_tokens_invalid", "b1_extra_token", "b1_duplicate_label"]
    raw = b1_raw(rows, usage={"prompt_tokens": 12})
    attempt = make_attempt(plan, response_raw=raw, transport_error="timeout")
    result = call_record(plan, [attempt], env.length, env.bcfg, env.policy.max_attempts)
    assert result.reason == "timeout" and result.usage == {"input_tokens": 12}
    assert result.answers_parsed is None
    with pytest.raises(ValueError, match="length"):
        call_record(plan, [attempt], None, env.bcfg, env.policy.max_attempts)


@pytest.mark.parametrize("usage,warning", [(26, False), (14, True), (25, True)])
def test_length_mismatch_compares_explicit_usage_sum(env, make_attempt, usage, warning):
    length = replace(env.length, length_tokens=14, usage_tokens=26)
    raw = json.dumps({"answers": {env.q.id: {"type": "noul", "noul": .8}},
                      "usage": {"input_tokens": usage}})
    call = call_record(env.plan, [make_attempt(env.plan, response_raw=raw)], length,
                       env.cfg, env.policy.max_attempts)
    assert call.status == "ok" and call.length.usage_tokens == 26
    assert ("length_mismatch" in call.warnings) is warning
    assert call.usage == {"input_tokens": usage}


def test_confidence_differs_is_ok_and_ordered(env, make_attempt):
    from jeveval.types import Request
    plan = replace(env.plan, request=Request("m", "s", {"q": {"type": "choice", "criteria": {"a": "a", "b": "b"}}}),
                   question_ids=["q"], question_types={"q": "choice"})
    raw = json.dumps({"answers": {"q": dict(type="choice", choice="b", confidence=.05,
                                            probabilities={"a": .8, "b": .2})}, "usage": {"input_tokens": 999}})
    call = call_record(plan, [make_attempt(plan, response_raw=raw)], env.length, env.cfg, env.policy.max_attempts)
    assert call.status == "ok" and call.reason is None
    assert call.warnings == ["extra_keys", "confidence_differs", "choice_not_argmax", "length_mismatch"]
    assert call.answers_parsed["q"].confidence == .05
