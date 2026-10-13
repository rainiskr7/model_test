"""무엇: 모집단·QStats 검증 · 입력: 기존 클래스/보정/MISSING fixture · 출력: 점수 대조 · 계약 §7-1~3·7-6."""

from copy import deepcopy
from dataclasses import replace

import pytest

from jeveval.score.population import population, qstats, score_table
from jeveval.types import ParsedAnswer, ScoreTable
from tests.score.population_support import answer, fixture, population_args, question, record


def assert_calibration(actual, expected):
    for key in ("ece", "brier", "log_loss"):
        assert actual[key] == (None if expected[key] is None else pytest.approx(expected[key]))
    for a, b in zip(actual["bins"], expected["bins"]):
        assert a == pytest.approx(b)
    assert len(actual["bins"]) == 15


def test_f1_and_calibration_fixtures_through_qstats():
    for case in fixture("f1_classes.json")["cases"]:
        probs = {c: 1 / len(case["configured_classes"]) for c in case["configured_classes"]}
        pairs = [(answer(p, probs), g) for p, g in zip(case["predicted"], case["gold"])]
        result = qstats("q", "success", "choice", pairs, 0)
        assert result.macro_f1 == case["expected"]["macro_f1"]
        assert result.classes == case["expected"]["class_stats"]
    for kind, case in fixture("calibration.json")["questions"].items():
        pairs = [(ParsedAnswer(kind, r["answer"], r["probs"], r["confidence"]), r["gold"])
                 for r in case["observations"]]
        result = qstats("q", "success", kind, pairs, 0)
        assert_calibration(result.calibration, case["expected"])
        assert sum(b["n"] for b in result.calibration["bins"]) == result.n_scored


def test_missing_fixture_through_population():
    records = []
    for n, case in enumerate(fixture("missing_mask.json")["requests"]):
        qs, parsed = [], {}
        for q in case["questions"]:
            options = {"NONE": "none"} if q["gold"] == "NONE" else None
            qs.append(question(q["id"], q["gold"], options=options, role=q["role"]))
            probs = {"NONE": 1.0} if options else {q["answer"]: q["confidence"],
                        "false" if q["answer"] == "true" else "true": 1 - q["confidence"]}
            parsed[q["id"]] = ParsedAnswer("choice" if options else "noul", q["answer"], probs, q["confidence"])
        # fixture의 present ID는 서로 다른 타입을 가리킨다. 다른 질문으로 묶어 집계한다.
        if qs[0].gold == "NONE":
            qs[0] = replace(qs[0], id="none")
            parsed["none"] = parsed.pop("present")
        records.append(record(qs, parsed, gid=str(n), status=case["status"]))
    args = population_args(records)
    before = deepcopy(args)
    result = population(**args)
    assert result.counts == dict(n_sampled=4, by_status=dict(ok=3, rejected=0, truncated=1, error=0), n_empty_mask=1)
    assert result.request == dict(n_scored=2, wrong=dict(num=0, den=2))
    assert result.questions["missing"].n_missing == 2
    assert result.questions["missing"].accuracy == dict(num=0, den=0)
    assert result.questions["missing"].macro_f1 is None
    assert result.questions["diag"].accuracy == dict(num=0, den=1)
    assert args == before


def test_warnings_are_per_question_recomputed_even_if_missing_and_b1():
    qs = [question(q, None if q == "missing" else "a", options={"a": "a", "b": "b"})
          for q in ("a", "b", "tie", "missing")]
    answers = {q.id: answer("b", {"a": .8, "b": .2}, .2) for q in qs}
    answers["tie"] = answer("b", {"a": .5, "b": .5}, .5)
    i, f, r = record(qs, answers)
    joint = population(**population_args([(i, f, r)]))
    assert {q: v.warnings["choice_not_argmax"] for q, v in joint.questions.items()} == dict(a=1, b=1, tie=0, missing=1)
    calls = [replace(f.calls[0], call_id=f.logical_id + "/" + q, answers_parsed={q: a}, warnings=[])
             for q, a in answers.items()]
    split = population(**population_args([(i, replace(f, calls=calls), r)]))
    assert joint == split
    # 파생 행동판에 원 칸의 경고가 남아 있어도 noul 질문 경고는 0이다.
    derived = record([question("act")], {"act": answer()}, set_name="kosgd")
    result = population(**population_args([derived], set_name="kosgd"))
    assert result.set_specific == {} and result.questions["act"].warnings == {"choice_not_argmax": 0}


def test_empty_cohort_keeps_question_shape_and_scoretable_roundtrip():
    i, f, r = record([question("q")], {"q": answer()}, status="error")
    result = population(**population_args([(i, f, r)]))
    assert result.questions["q"].n_scored == 0
    assert result.questions["q"].calibration["ece"] is None
    assert result.questions["q"].warnings == {"choice_not_argmax": 0}
    table = score_table(model="m", set="synthetic", variant="v", run_id="r",
                        populations={"test": result}, cost={})
    assert ScoreTable.from_dict(table.to_dict()) == table
    result.counts["n_sampled"] = 10
    assert table.populations["test"].counts["n_sampled"] == 1


@pytest.mark.parametrize("defect", ["duplicate", "missing_final", "wrong_outcome", "dev", "duplicate_group"])
def test_reject_population_mismatch(defect):
    entry = record([question("q")], {"q": answer()})
    args = population_args([entry])
    if defect == "duplicate":
        args["outcomes"] *= 2
    elif defect == "missing_final":
        args["finals"] = []
    elif defect == "wrong_outcome":
        args["outcomes"] = [replace(entry[2], wrong=True)]
    elif defect == "dev":
        args["outcomes"] = [replace(entry[2], stage="dev")]
    else:
        args = population_args([entry, record([question("q")], {"q": answer()}, iid="j")])
    with pytest.raises(ValueError):
        population(**args)
