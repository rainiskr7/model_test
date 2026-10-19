"""무엇: 질문 투영 경계 · 입력: 가변 질문·무효 요청·슬롯 · 출력: 손계산 관측 · 계약 §7-4b."""

from dataclasses import replace

import pytest

from jeveval.score.question_outcomes import observations, align
from tests.score.population_support import answer, question, record


def project(qs, answers, **kwargs):
    item, final, _ = record(qs, answers, **kwargs)
    return observations([final], {final.logical_id: item}, kwargs.get("stage", "test"))


def test_question_confidence_not_request_min_and_invalid_inherits():
    qs = [question("a"), question("b", None), question("d", role="diagnostic")]
    values = {"a": answer(confidence=.9), "b": answer(confidence=.1), "d": answer(confidence=.5)}
    rows = project(qs, values)
    assert [r.confidence for r in rows] == [.9, .1, .5]
    invalid = project(qs, values, status="error")
    assert all(not r.valid and r.confidence is None and r.answer is None for r in invalid)


def test_variable_aspect_absence_differs_from_missing_and_false():
    first = record([question("aspect_1", "false")], {"aspect_1": answer("false")}, gid="1")
    second = record([question("aspect_1"), question("aspect_2", None)],
                    {"aspect_1": answer(), "aspect_2": answer()}, gid="2")
    rows = observations([r[1] for r in (first, second)], {r[1].logical_id: r[0] for r in (first, second)}, "test")
    absent = next(r for r in rows if r.group_id == "1" and r.question_id == "aspect_2")
    missing = next(r for r in rows if r.group_id == "2" and r.question_id == "aspect_2")
    assert not absent.present and missing.present and missing.gold is None
    assert next(r for r in rows if r.group_id == "1" and r.question_id == "aspect_1").gold == "false"


def test_slots_swapped_are_one_correct_unit_with_min_confidence():
    options = {"a/x": "x", "b/y": "y", "NONE": "none"}
    qs = [question("one", "a/x", "ongoing_slot_1", options), question("two", "b/y", "ongoing_slot_2", options)]
    rows = project(qs, {"one": answer("b/y", {"b/y": 1}, .8), "two": answer("a/x", {"a/x": 1}, .7)})
    assert len(rows) == 1 and rows[0].question_id == "ongoing_bundle"
    assert rows[0].confidence == .7 and rows[0].wrong is False
    with pytest.raises(ValueError):
        project([qs[0], replace(qs[1], gold=None)], {"one": answer(), "two": answer()})


def test_question_only_in_test_has_absent_dev():
    dev = project([question("a")], {"a": answer()}, stage="dev")
    test = project([question("a"), question("b")], {"a": answer(), "b": answer()})
    dev, test = align(dev, test)
    assert next(r for r in dev if r.question_id == "b").present is False


def test_both_slots_missing_excluded_but_none_bundle_has_gold():
    options = {"NONE": "none", "a/x": "x"}
    qs = [question("one", None, "ongoing_slot_1", options), question("two", None, "ongoing_slot_2", options)]
    values = {qid: answer("NONE", {"NONE": 1}) for qid in ("one", "two")}
    assert project(qs, values)[0].gold is None
    assert project([replace(q, gold="NONE") for q in qs], values)[0].gold == "NONE"
