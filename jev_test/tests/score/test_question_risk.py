"""무엇: 질문 위험 손계산 · 입력: 4묶음/경계 · 출력: 분모·τ·상태 · 계약 §7-4b."""

from dataclasses import replace

import pytest

from jeveval.score.question_risk import calculate
from jeveval.types.outcomes import QuestionOutcome


def row(i, stage, q="a", **changes):
    base = QuestionOutcome(f"s:{i}:i", str(i), stage, "ok", True, q, "success", "x", "noul",
                           "true", "true", .9, False, True, 10, {})
    return replace(base, **changes)


def test_four_groups_two_questions_invalid_missing_absence_and_diagnostics():
    dev = [row(i, "dev", q) for q in ("a", "b") for i in range(4)]
    test = [row(i, "test", "a") for i in range(4)]
    test += [row(0, "test", "b"), row(1, "test", "b", valid=False, status="error", confidence=None, wrong=None),
             row(2, "test", "b", gold=None, wrong=None), row(3, "test", "b", present=False, gold=None, wrong=None)]
    dev = [replace(r, role="diagnostic") if r.question_id == "b" else r for r in dev]
    test = [replace(r, role="diagnostic") if r.question_id == "b" else r for r in test]
    result = calculate(dev, test)
    assert set(result["questions"]) == {"a"} and set(result["diagnostic"]) == {"b"}
    b = result["diagnostic"]["b"]
    assert b["denominator"]["test"] == dict(n_groups=4, n_absent=1, n_missing=1, n_denom=2, n_invalid=1, n_false=0, n_none=0)
    for cell in b["by_tau"].values():
        assert cell["coverage"] == {"num": 1, "den": 2} and cell["status"] == "UNDERPOWERED"


@pytest.mark.parametrize("case,status,n", [("wrong_dev", "NO_THRESHOLD", None), ("zero", "UNDERPOWERED", 0),
                                           ("ties", "NO_THRESHOLD", None), ("meets", "MEETS", 300)])
def test_no_threshold_zero_acceptance_confidence_ties_and_cp(case, status, n):
    dev = [row(0, "dev", wrong=case in ("wrong_dev", "ties"))]
    if case == "ties":
        dev.append(row(1, "dev"))
    test = [row(i, "test", confidence=.1 if case == "zero" else .9) for i in range(300)]
    cell = calculate(dev, test)["questions"]["a"]["by_tau"]["0.01"]
    assert cell["status"] == status and cell["n_accepted"] == n


def test_tau_selection_differs_without_rounded_risk():
    dev = [row(i, "dev", confidence=.9 if i < 50 else .8, wrong=i == 99) for i in range(100)]
    test = [row(i, "test") for i in range(4)]
    cells = calculate(dev, test)["questions"]["a"]["by_tau"]
    assert cells["0.01"]["t_star"] == .9
    assert cells["0.02"]["t_star"] == cells["0.05"]["t_star"] == .8


@pytest.mark.parametrize("mode", ["meets", "no_threshold", "zero", "fails", "masked_invalid"])
def test_single_question_core_exactly_matches_original_request_risk_all_taus(mode):
    from jeveval.score.question_outcomes import observations
    from jeveval.score.risk import risk_cell
    from jeveval.score.threshold import TAUS, select
    from jeveval.score.tasks import outcome
    from jeveval.types import LengthInfo
    from tests.score.population_support import answer, question, record
    stages = {}
    for stage in ("dev", "test"):
        records = []
        for i in range(300):
            wrong = (stage == "dev" and mode == "no_threshold") or (stage == "test" and mode == "fails")
            missing = mode == "masked_invalid" and i == 0
            status = "error" if mode == "masked_invalid" and i == 1 else "ok"
            confidence = .1 if stage == "test" and mode == "zero" else .9
            item, final, _ = record([question("q", None if missing else "true")],
                {"q": answer("false" if wrong else "true", confidence=confidence)}, gid=str(i), stage=stage, status=status)
            final = replace(final, calls=[replace(final.calls[0], length=LengthInfo(10, 5, 100, 5))])
            records.append((item, final, outcome(final, item, stage)))
        stages[stage] = records
    items = {f.logical_id: item for item, f, _ in stages["test"]}
    projected = {s: observations([f for _, f, _ in rows], {f.logical_id: i for i, f, _ in rows}, s) for s, rows in stages.items()}
    cells = calculate(projected["dev"], projected["test"])["questions"]["q"]["by_tau"]
    dev, test = ([r for _, _, r in stages[s]] for s in ("dev", "test"))
    for tau in TAUS:
        request = risk_cell(tau=tau, threshold=select(dev, tau), dev=dev, test=test, test_items=items)
        expected = {k: getattr(request, k) if k in ("status", "t_star") else request.test[k] for k in cells[tau]}
        assert cells[tau] == expected
