"""무엇: 채점→위험 분포 경계 · 입력: fixture·합성 질문 · 출력: 분모·분포 검증 · 계약 §7-3~4."""

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import pytest

from jeveval.run.length import length_bucket as run_bucket
from jeveval.score.risk import risk_cell
from jeveval.score.risk_mix import length_bucket
from jeveval.score.tasks import outcome
from jeveval.score.threshold import select
from jeveval.types import BoundQuestion, CallRecord, FinalRecord, Item, LengthInfo, ParsedAnswer


def question(qid="q", gold="true", role="success", label="synthetic", options=None):
    return BoundQuestion(qid, role, "choice" if options else "noul", "", options,
                         None if options else {"true": "yes", "false": "no"}, label, gold)


def sample(index=0, *, questions=None, answers=None, status="ok", length=12,
           set_name="synthetic", service=None, stratum=None):
    questions = questions or [question()]
    item = Item(set_name, str(index), "i", "", questions,
                dict(service=service, stratum=stratum, flags=[]), None)
    lid = f"{set_name}:{index}:i"
    answers = answers or {q.id: ParsedAnswer(q.type, q.gold or "true", {}, .9) for q in questions}
    call = CallRecord(lid, int(length is not None), status, None, [], "a" * 64,
                      None if length is None else LengthInfo(length, 1, 99999, 0), None, answers)
    return item, outcome(FinalRecord(lid, status, None, False, [], [call]), item, "test")


def cell(pairs, dev=None):
    if dev is None:
        dev = [replace(sample()[1], stage="dev")]
    return risk_cell(tau="0.02", threshold=select(dev, "0.02"), dev=dev,
                     test=[row for _, row in pairs], test_items={row.logical_id: item for item, row in pairs})


def test_missing_mask_fixture_through_tasks_threshold_and_risk():
    fixture = json.loads((Path(__file__).parents[1] / "fixtures/scoring/missing_mask.json").read_text())
    pairs = []
    for i, case in enumerate(fixture["requests"]):
        questions = [question(q["id"], q["gold"], q["role"]) for q in case["questions"]]
        answers = {q["id"]: ParsedAnswer("noul", q["answer"], {}, q["confidence"]) for q in case["questions"]}
        pairs.append(sample(i, questions=questions, answers=answers, status=case["status"]))
    dev = [replace(row, stage="dev") for _, row in pairs]
    result = cell(pairs, dev)
    assert result.dev == dict(n_groups=4, n_denom=3, n_empty_mask=1, n_accepted=2, k_errors=0)
    assert result.test["coverage"] == dict(num=2, den=3)
    assert result.by_status == dict(ok=2, rejected=0, truncated=1, error=0)
    assert result.accepted_mix["by_n_questions"] == {
        "2": dict(sampled=2, n=1, k=0), "1": dict(sampled=1, n=1, k=0)}
    assert "missing" not in result.accepted_mix["by_class"]
    assert result.diagnostic_error_in_accepted == {"diag": dict(n=1, wrong=1)}


def test_kosgd_fixed_slot_class_request_error_and_multiservice():
    options = {"A/a": "a", "B/b": "b", "NONE": "none"}
    questions = [question("s1", "A/a", label="ongoing_slot_1", options=options),
                 question("s2", "B/b", label="ongoing_slot_2", options=options),
                 question("diag", role="diagnostic")]
    answers = {qid: ParsedAnswer("choice", a, {}, .9)
               for qid, a in [("s1", "B/b"), ("s2", "A/a"), ("diag", "false")]}
    correct = sample(0, questions=questions, answers=answers, set_name="kosgd", service=["A", "B"])
    wrong_answers = dict(answers, s1=ParsedAnswer("choice", "A/a", {}, .9))
    wrong = sample(1, questions=questions, answers=wrong_answers, set_name="kosgd", service=["A"])
    pairs = [correct, wrong]
    before = deepcopy(pairs)
    result = cell(pairs)
    assert result.test["k_errors"] == 1
    assert result.accepted_mix["by_class"]["s1"] == {"A/a": dict(sampled=2, n=2, k=1)}
    assert result.accepted_mix["by_service"] == {"A": dict(sampled=2, n=2, k=1), "B": dict(sampled=1, n=1, k=0)}
    assert sum(x["n"] for x in result.accepted_mix["by_service"].values()) > result.test["n_accepted"]
    assert result.accepted_mix["by_n_questions"] == {"2": dict(sampled=2, n=2, k=1)}
    assert result.diagnostic_error_in_accepted == {"diag": dict(n=2, wrong=2)}
    assert pairs == before


def test_klue_strata_and_korfin_one_to_eight_success_questions():
    pairs = [sample(i, set_name="klue_mrc_answerable", stratum=s, status=status)
             for i, (s, status) in enumerate([("news", "ok"), ("news", "error"), ("wiki", "ok")])]
    result = cell(pairs)
    assert result.accepted_mix["by_stratum"] == {
        "news": dict(sampled=2, n=1, k=0), "wiki": dict(sampled=1, n=1, k=0)}
    assert result.accepted_mix["by_service"] is None
    pairs = [sample(n, set_name="korfin_asc", questions=[question(f"aspect_{i}") for i in range(n)])
             for n in range(1, 9)]
    assert cell(pairs).accepted_mix["by_n_questions"] == {str(n): dict(sampled=1, n=1, k=0) for n in range(1, 9)}


@pytest.mark.parametrize("n,expected", [(4096, "le_4096"), (4097, "le_8192"), (8192, "le_8192"),
                                       (8193, "le_16384"), (16384, "le_16384"), (16385, "gt_16384")])
def test_length_boundaries_match_run_and_risk(n, expected):
    assert length_bucket(n) == run_bucket(n) == expected
    assert cell([sample(length=n)]).by_length_bucket[expected] == dict(sampled=1, n_valid=1, n=1, k=0)


def test_unmeasured_and_empty_mask_partition_and_no_threshold():
    pairs = [sample(i, length=n) for i, n in enumerate([4096, 4097, 8192, 8193, 16384, 16385])]
    pairs += [sample(6, length=None, status="error"), sample(7, status="rejected"),
              sample(8, questions=[question(gold=None)], status="error", length=None)]
    result = cell(pairs)
    assert result.by_length_bucket["unmeasured"] == dict(sampled=1, n_valid=0, n=0, k=0)
    assert sum(b["sampled"] for b in result.by_length_bucket.values()) == result.test["n_denom"] == 8
    assert result.test["n_empty_mask"] == 1
    result = cell(pairs, dev=[])
    assert result.status == "NO_THRESHOLD" and result.test["n_accepted"] is None
    assert result.test["coverage"] == dict(num=0, den=8)
    assert all(b["n"] == b["k"] == 0 for b in result.by_length_bucket.values())
    assert result.by_length_bucket["le_4096"]["n_valid"] == 1


def test_diagnostic_missing_gold_is_not_an_error():
    result = cell([sample(questions=[question(), question("diag", None, "diagnostic")])])
    assert result.diagnostic_error_in_accepted == {}
