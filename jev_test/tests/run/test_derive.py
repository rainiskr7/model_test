"""무엇: 파생 판 짝 시험 · 입력: 전체판/질문 · 출력: 보존·거르기·사본 · 계약 §5-4·§8-6 K·⑤d R2."""

from dataclasses import replace
import json

import pytest

from jeveval.run.derive import derive_actions_only, derive_stage
from jeveval.run.outcome import call_record, final_record
from jeveval.run.plan_calls import plan_calls


def full_record(env, make_attempt, b1_raw, kind):
    """실제 planner/outcome으로 세 질문 전체판을 구성한다."""
    qids = ["action_a", "ongoing", "action_b"]
    item = replace(env.item, questions=[replace(env.q, id=q) for q in qids])
    cfg = env.cfg if kind == "systemone" else env.bcfg
    plans = plan_calls(item, env.task, cfg, env.b1)
    raw = (json.dumps({"answers": {q: {"type": "noul", "noul": .8} for q in qids}})
           if kind == "systemone" else b1_raw([{"token": "A", "logprob": -1}, {"token": "B", "logprob": -2}]))
    calls = [call_record(p, [make_attempt(p, response_raw=raw)], env.length, cfg) for p in plans]
    return item, final_record(env.plan.logical_id, plans, calls)


@pytest.mark.parametrize("kind", ["systemone", "b1"])
@pytest.mark.parametrize("status", ["ok", "error", "rejected", "truncated"])
def test_derive_preserves_state_and_original(tmp_path, env, make_attempt, b1_raw, kind, status):
    """원본 오류·경고·over-limit와 호출 관측값을 보존하며 순서와 별칭을 검사한다."""
    item, full = full_record(env, make_attempt, b1_raw, kind)
    if status != "ok":
        index = 0 if kind == "systemone" else 1
        calls = list(full.calls)
        calls[index] = replace(calls[index], status=status, reason="reason", answers_parsed=None)
        full = replace(full, status=status, reason="reason", calls=calls,
                       answered_over_limit=True, warnings=["original"])
    before = full.to_dict()
    # action_qids 반대 순서여도 원본 호출/맵 순서를 유지한다.
    derived = derive_actions_only(full, ["action_b", "action_a"], [q.id for q in item.questions], "full/run")
    assert (derived.status, derived.reason, derived.answered_over_limit, derived.warnings) == (
        full.status, full.reason, full.answered_over_limit, full.warnings)
    assert derived.derived_from == "full/run"
    selected = full.calls if kind == "systemone" else [full.calls[0], full.calls[2]]
    for actual, original in zip(derived.calls, selected, strict=True):
        assert replace(actual, answers_parsed=original.answers_parsed) == original
    if kind == "systemone":
        assert (None if derived.calls[0].answers_parsed is None else list(derived.calls[0].answers_parsed)) == (
            ["action_a", "action_b"] if status == "ok" else None)
    else:
        assert [c.call_id for c in derived.calls] == [c.call_id for c in selected]
    derived.warnings.append("mutated")
    derived.calls[0].warnings.append("mutated")
    if derived.calls[0].answers_parsed:
        next(iter(derived.calls[0].answers_parsed.values())).probs["true"] = 0
    assert full.to_dict() == before
    with pytest.raises(ValueError, match="question IDs"):
        derive_actions_only(full, ["missing"], [q.id for q in item.questions], "full/run")


def test_derive_stage_complete_ids_and_empty(env, make_attempt, b1_raw):
    """완료 단계의 Item 연결·중복·누락·빈 단계를 확인한다."""
    item, full = full_record(env, make_attempt, b1_raw, "b1")
    expected = derive_actions_only(full, ["action_a"], [q.id for q in item.questions], "full/run")
    assert derive_stage([full], [item], ["action_a"], "full/run") == [expected]
    assert derive_stage([], [], ["action_a"], "full/run") == []
    for finals, items in (([], [item]), ([full], []), ([full, full], [item]), ([full], [item, item])):
        with pytest.raises(ValueError):
            derive_stage(finals, items, ["action_a"], "full/run")


def test_derive_rejects_mismatched_full_calls_or_answers(env, make_attempt, b1_raw):
    """다른 전체판의 질문 목록으로 파생을 가장할 수 없다."""
    for kind in ("systemone", "b1"):
        _, full = full_record(env, make_attempt, b1_raw, kind)
        with pytest.raises(ValueError):
            derive_actions_only(full, ["action_a"], ["action_a"], "full/run")
