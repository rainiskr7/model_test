"""무엇: 호출 계획 검증 · 입력: 합성 항목·B1 fixture · 출력: 바이트·오류/대응표 · 계약 §2·§8-6."""

from copy import deepcopy
from dataclasses import replace
import hashlib
import json

import pytest

from jeveval.contract.request import request_bytes
from jeveval.run.outcome import call_record
from jeveval.run.plan_calls import plan_calls
from jeveval.types import B1Config, BoundQuestion, Rendered


def test_systemone_bytes_order_and_no_input_mutation(env):
    """질문 순서·바이트·해시와 입력 불변을 함께 확인한다."""
    item = replace(env.item, questions=[replace(env.q, id="z"), replace(env.q, id="a")])
    before = deepcopy(item)
    plan, = plan_calls(item, env.task, env.cfg, None)
    assert plan.call_id == plan.logical_id == "synthetic:g1:i1"
    assert plan.question_ids == ["z", "a"] and plan.question_types == {"z": "noul", "a": "noul"}
    assert plan.body == request_bytes(plan.request)
    assert plan.request_sha256 == hashlib.sha256(plan.body).hexdigest()
    assert plan.local_errors == [] and plan.b1_call is None and item == before


def test_b1_prompt_fixture(env, fixture_json):
    """설정 문구·질문별 호출·라벨 순서 토큰과 B1Call 보존을 검증한다."""
    source = fixture_json("b1/prompt.json")
    config = B1Config.from_dict(source["config"])
    item = replace(env.item, state_fields=source["rendered"]["state"],
                   questions=[BoundQuestion.from_dict(c["question"]) for c in source["cases"]])
    cfg = replace(env.bcfg, b1={"label_token_ids": {"Z": 9, "Y": 7, "X": 5}})
    plans = plan_calls(item, env.task, cfg, config)
    assert [p.call_id for p in plans] == ["synthetic:g1:i1/pick", "synthetic:g1:i1/ready"]
    for plan, case in zip(plans, source["cases"]):
        assert not plan.local_errors
        # fixture는 이미 렌더된 입력용이다. 여기서는 plain_text 렌더를 한 번 더 거친다.
        expected = deepcopy(case["expected"])
        raw_state = source["rendered"]["state"]
        user = expected["messages"][1]["content"]
        assert user.startswith(raw_state)
        expected["messages"][1]["content"] = raw_state.strip() + user[len(raw_state):]
        assert plan.rendered == Rendered(raw_state.strip(), len(raw_state.strip()))
        assert item.state_fields == raw_state
        for key, value in expected.items():
            assert getattr(plan.b1_call, key) == value
        assert json.loads(plan.body)["allowed_token_ids"] == [5, 7, 9][:len(plan.b1_call.label_order)]
        assert plan.request_sha256 == hashlib.sha256(plan.body).hexdigest()


@pytest.mark.parametrize("kind", ["systemone", "b1"])
@pytest.mark.parametrize("failure", ["duplicate", "empty", "casefold", "render"])
def test_item_errors_cover_all_unique_calls(env, kind, failure):
    """항목 오류가 B1 일부 전송으로 새지 않고 중복 호출 ID도 만들지 않는다."""
    q = env.q
    if failure in ("empty", "casefold"):
        q = replace(q, type="choice", options={} if failure == "empty" else {"A": "a", "a": "b"})
    questions = [q, replace(env.q, id="other"), q] if failure == "duplicate" else [q, replace(env.q, id="other")]
    item = replace(env.item, questions=questions, state_fields={} if failure == "render" else "원문")
    cfg = env.cfg if kind == "systemone" else env.bcfg
    plans = plan_calls(item, env.task, cfg, env.b1)
    assert len(plans) == (1 if kind == "systemone" else 2)
    assert len({p.call_id for p in plans}) == len(plans)
    assert plans[0].local_errors
    for plan in plans:
        assert plan.local_errors == plans[0].local_errors
        assert plan.body == b"" and plan.request_sha256 == hashlib.sha256(b"").hexdigest()
        assert call_record(plan, [], None, cfg, env.policy.max_attempts).reason == "request_contract"
        if failure == "render":
            assert plan.rendered == Rendered("", 0)


def test_b1_call_error_is_local_and_keeps_available_call(env):
    """63개 선택지 실패는 다른 질문을 막지 않고 토큰 누락에는 만든 대응표를 남긴다."""
    q = replace(env.q, type="choice", options={f"o{i}": "설명" for i in range(63)})
    item = replace(env.item, questions=[q, replace(env.q, id="other")])
    plans = plan_calls(item, env.task, env.bcfg, env.b1)
    assert plans[0].local_errors and plans[0].b1_call is None
    assert not plans[1].local_errors and plans[1].body
    cfg = replace(env.bcfg, b1={"label_token_ids": {"A": 0}})
    plan, = plan_calls(env.item, env.task, cfg, env.b1)
    assert plan.local_errors and plan.b1_call.label_map == {"A": "true", "B": "false"}
    record = call_record(plan, [], env.length, cfg, env.policy.max_attempts)
    assert record.label_map == plan.b1_call.label_map and record.length is None
    assert record.attempts == 0 and record.usage is record.answers_parsed is None


@pytest.mark.parametrize("missing", ["served_name", "b1_config", "label_token_ids", "b1"])
def test_incomplete_config_stops(env, missing):
    """요청 오류와 달리 미완 설정은 계획 단계 자체를 중단한다."""
    cfg, config = env.bcfg, env.b1
    if missing == "b1_config":
        config = None
    elif missing == "label_token_ids":
        cfg = replace(cfg, b1={"label_token_ids": None})
    else:
        cfg = replace(cfg, **{missing: None})
    with pytest.raises(ValueError):
        plan_calls(env.item, env.task, cfg, config)


def test_mapping_fixture_through_call_record(env, fixture_json, make_attempt, b1_raw):
    """기존 choice 라벨 대응을 응답 파싱까지 연결한다."""
    source = fixture_json("b1/label_mapping.json")
    q = replace(env.q, type="choice", options=source["criteria"])
    plan, = plan_calls(replace(env.item, questions=[q]), env.task, env.bcfg, env.b1)
    assert plan.b1_call.label_map == source["expected"]["label_map"]
    for line in source["expected"]["option_lines"]:
        assert line in plan.b1_call.messages[1]["content"]
    raw = b1_raw([{"token": label, "logprob": -1.0} for label in source["labels"]])
    result = call_record(plan, [make_attempt(plan, response_raw=raw)], env.length, env.bcfg, env.policy.max_attempts)
    answer = result.answers_parsed[q.id]
    assert result.status == "ok" and answer.answer == "NONE"
    assert answer.probs == pytest.approx({"NONE": 1 / 3, "a": 1 / 3, "z": 1 / 3})
