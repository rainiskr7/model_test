"""무엇: 성공 질문 F1 입력 · 입력: 합성 Item/outcome · 출력: 마스크/고정 칸/pooled · 계약 §7-2·7-7."""

from copy import deepcopy
from dataclasses import replace

from jeveval.score.observations import observations, question_ids
from tests.score.population_support import answer, question, record


def test_only_success_gold_ok_and_functionchat_tool_excluded():
    qs = [question("q"), question("missing", gold=None), question("diagnostic", role="diagnostic"),
          question("tool", label="fc:tool")]
    item, final, row = record(qs, {q.id: answer() for q in qs}, set_name="fc_call_decision")
    args = [row, replace(row, status="error")], {row.logical_id: item}
    before = deepcopy(args)
    result = observations(*args)
    assert [o.question_id for o in result] == ["q"]
    assert question_ids(args[1]) == ["missing", "q"]
    assert args == before


def test_kosgd_gold_uses_catalog_order_and_missing_is_empty():
    options = {"a": "a", "b": "b", "NONE": "none"}
    qs = [question("q1", "b", "ongoing_slot_1", options), question("q2", "a", "ongoing_slot_2", options)]
    answers = {"q1": answer("b", dict(a=0., b=1., NONE=0.)), "q2": answer("a", dict(a=1., b=0., NONE=0.))}
    item, _, row = record(qs, answers, set_name="kosgd")
    result = observations([row], {row.logical_id: item})
    assert [(o.answer, o.gold) for o in result] == [("b", "a"), ("a", "b")]
    item, _, row = record([replace(q, gold=None) for q in qs], answers, set_name="kosgd")
    assert observations([row], {row.logical_id: item}) == []


def test_korfin_pooled_keeps_multiple_aspects_in_same_group():
    qs = [question("a1", label="korfin:sentiment"), question("a2", label="korfin:sentiment")]
    item, _, row = record(qs, {q.id: answer() for q in qs}, set_name="korfin_asc")
    result = observations([row], {row.logical_id: item})
    pooled = [o for o in result if o.question_id == "aspect"]
    assert len(pooled) == 2 and {o.group_id for o in pooled} == {item.group_id}
    assert question_ids({row.logical_id: item}) == ["a1", "a2", "aspect"]
