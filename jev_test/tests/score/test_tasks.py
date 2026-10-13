"""무엇: 요청 채점 경계 검증 · 입력: 합성 Item·기존 fixture · 출력: 결과 대조 · 계약 §7-1~3·§7-8."""

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import pytest

from jeveval.score.tasks import outcome
from jeveval.score.threshold import threshold_file
from jeveval.types import BoundQuestion, CallRecord, FinalRecord, Item, LengthInfo, ParsedAnswer


ROOT = Path(__file__).parents[1] / "fixtures/scoring"


def question(qid, gold="true", role="success", label="synthetic", options=None):
    return BoundQuestion(qid, role, "choice" if options else "noul", "synthetic",
                         options, None if options else {"true": "yes", "false": "no"}, label, gold)


def inputs(questions, answers=None, status="ok"):
    item = Item("synthetic", "g", "i", "state", questions,
                {"service": ["s"], "stratum": None, "flags": []}, None)
    if answers is None:
        answers = {q.id: ParsedAnswer(q.type, q.gold or "true", {}, .9) for q in questions}
    call = CallRecord("synthetic:g:i", 1, status, None, [], "a" * 64,
                      LengthInfo(12, 7, 100, 5), None, answers)
    return item, FinalRecord("synthetic:g:i", status, None, False, [], [call])


def test_missing_fixture_through_outcome_and_threshold():
    fixture = json.loads((ROOT / "missing_mask.json").read_text())
    results = []
    for index, case in enumerate(fixture["requests"]):
        questions = [question(q["id"], q["gold"], q["role"]) for q in case["questions"]]
        answers = {q["id"]: ParsedAnswer("noul", q["answer"], {}, q["confidence"])
                   for q in case["questions"]}
        item, final = inputs(questions, answers, case["status"])
        item = replace(item, group_id=str(index))
        final = replace(final, logical_id=f"synthetic:{index}:i")
        result = outcome(final, item, "dev")
        for key, value in case["expected"].items():
            actual = (sum(g is None for g in result.gold.values()) if result.valid else 0
                      ) if key == "n_missing" else getattr(result, key)
            assert actual == value
        results.append(result)
    threshold = threshold_file(model="m", set="synthetic", variant="full", run_id="r",
                               dev_sha256="a" * 64, dev_nbytes=0, dev=results)
    assert {k: threshold.dev_input[k] for k in fixture["expected"]} == fixture["expected"]
    assert threshold.dev_input["n_groups"] == 4


def test_kosgd_fixture_bundles_keep_fixed_gold_and_success_confidence():
    fixture = json.loads((ROOT / "kosgd_slots.json").read_text())
    options = {key: key for key in [*fixture["catalog_order"], "NONE"]}
    for case in fixture["cases"]:
        questions = [question(f"slot_{i}", g, label=f"ongoing_slot_{i}", options=options)
                     for i, g in enumerate(case["expected"]["fixed_gold"], 1)]
        questions += [question("act"), question("diag", role="diagnostic")]
        answers = {f"slot_{i}": ParsedAnswer("choice", a, {}, .7 + .1 * i)
                   for i, a in enumerate(case["predicted"], 1)}
        answers.update(act=ParsedAnswer("noul", "true", {}, .99),
                       diag=ParsedAnswer("noul", "false", {}, .01))
        item, final = inputs(list(reversed(questions)), answers)
        before = deepcopy((item, final))
        result = outcome(final, item, "test")
        assert result.wrong == (not case["expected"]["group_correct"])
        assert not result.mask_empty and result.s == pytest.approx(.8)
        assert [result.gold[f"slot_{i}"] for i in (1, 2)] == case["expected"]["fixed_gold"]
        assert list(result.gold) == list(result.roles) == [q.id for q in item.questions]
        assert (item, final) == before
        # 칸 묶음이 맞아도 행동 질문이 틀리면 요청 오류다.
        final.calls[0].answers_parsed["act"] = ParsedAnswer("noul", "false", {}, .99)
        assert outcome(final, item, "test").wrong is True


@pytest.mark.parametrize("status", ["ok", "truncated", "rejected", "error"])
@pytest.mark.parametrize("golds", [(None, "b"), ("b", None), (None, None)])
def test_kosgd_partial_and_total_missing(status, golds):
    questions = [question(f"q{i}", g, label=f"ongoing_slot_{i}", options={"b": "b", "NONE": "-"})
                 for i, g in enumerate(golds, 1)]
    item, final = inputs(questions, status=status)
    if golds != (None, None):
        with pytest.raises(ValueError, match="partially MISSING"):
            outcome(final, item, "dev")
    else:
        result = outcome(final, item, "dev")
        assert result.mask_empty and result.wrong is None
        assert result.s == (.9 if status == "ok" else None)


@pytest.mark.parametrize("stage", ["dev", "test", "extra"])
@pytest.mark.parametrize("status", ["ok", "truncated", "rejected", "error"])
def test_status_controls_scoring_even_with_partial_b1_answers(stage, status):
    item, final = inputs([question("a"), question("b")], status=status)
    if status != "ok":
        final.calls[0].answers_parsed.pop("b")
    result = outcome(final, item, stage)
    assert (result.stage, result.status, result.valid) == (stage, status, status == "ok")
    assert result.s == (.9 if result.valid else None)
    assert result.wrong == (False if result.valid else None)
    assert result.answer == ({"a": "true", "b": "true"} if result.valid else None)
    assert not result.mask_empty and result.length_max == 12


@pytest.mark.parametrize("defect", ["missing", "extra", "duplicate", "null"])
def test_answer_key_errors(defect):
    item, final = inputs([question("a"), question("b")])
    call = final.calls[0]
    if defect == "missing":
        call.answers_parsed.pop("b")
    elif defect == "extra":
        call.answers_parsed["extra"] = call.answers_parsed["a"]
    elif defect == "duplicate":
        final.calls.append(replace(call, call_id=call.call_id + "/again"))
    else:
        final.calls[0] = replace(call, answers_parsed=None)
    with pytest.raises(ValueError, match="question ID"):
        outcome(final, item, "test")


def test_b1_merge_lengths_and_independent_metadata():
    item, final = inputs([question("a"), question("b")])
    call = final.calls[0]
    calls = [replace(call, call_id=call.call_id + "/" + q, answers_parsed={q: a},
                     length=LengthInfo(n, 7, 100, 5))
             for (q, a), n in zip(call.answers_parsed.items(), [12, 42])]
    final = replace(final, calls=list(reversed(calls)))
    result = outcome(final, item, "test")
    assert result.answer == {"a": "true", "b": "true"} and result.length_max == 42
    result.meta["flags"].append("changed")
    result.meta["service"].append("changed")
    assert item.meta == {"service": ["s"], "stratum": None, "flags": []}
    final.calls[0] = replace(final.calls[0], length=None)
    assert outcome(final, item, "test").length_max == 12
    final.calls[1] = replace(final.calls[1], length=None)
    assert outcome(final, item, "test").length_max is None


def test_logical_id_and_stage_validation():
    item, final = inputs([question("a")])
    with pytest.raises(ValueError, match="logical_id"):
        outcome(replace(final, logical_id="wrong:g:i"), item, "test")
    with pytest.raises(ValueError, match="stage"):
        outcome(final, item, "unknown")
