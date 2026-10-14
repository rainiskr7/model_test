"""무엇: 분포/답 정책 오류 주입 · 입력: 비대칭/격차/score fixture · 출력: 별도 정책 판정 · 계약 T-f."""

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import pytest

from jeveval.t0.compare import compare_request
from jeveval.t0.response import validate_response
from jeveval.types.t0 import T0Tolerance

CASES = json.loads((Path(__file__).parents[1] / "fixtures/t0/comparisons.json").read_text())["cases"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_comparison_policy(case):
    question = dict(type=case["type"])
    if case["type"] == "choice":
        question["criteria"] = {k: k for k in case["reference"]["probabilities"]}
    questions = {"q": question}
    answers = [validate_response(json.dumps({"answers":{"q":dict(type=case["type"], **case[side])}}),
                                 questions, 0) for side in ("reference", "server")]
    assert all(a.reason is None for a in answers)
    tolerance = T0Tolerance("measured", "PASS", 0, case["tol"], [], 5)
    result = compare_request(case["id"], questions, *answers, {"q":tolerance}, 0)
    row = result.questions[0]
    assert result.status == case["status"]
    assert row.distribution_ok == case["distribution_ok"]
    assert row.answer_changed == case["changed"] and row.change_allowed == case["allowed"]
    assert result.n_expected == result.n_compared == 1


def test_score_expected_difference_and_diagnostic_only(response_fixture):
    questions = {"grade": response_fixture["questions"]["grade"]}
    answer = response_fixture["valid"]["answers"]["grade"]
    reference = validate_response(json.dumps({"answers":{"grade":answer}}), questions, 5e-5)
    server_answer = deepcopy(answer)
    server_answer.update(score=2.0003)
    server_answer["probabilities"].update({"0":.1999,"4":.2001})
    server_answer["confidence"] = .2001
    server = validate_response(json.dumps({"answers":{"grade":server_answer}}), questions, 5e-5)
    assert reference.reason is server.reason is None
    tol = T0Tolerance("measured", "PASS", 0, .0001, [], 5)
    result = compare_request("score", questions, reference, server, {"grade":tol}, 5e-5)
    assert result.status == "PASS"
    row = result.questions[0]
    assert row.answer_changed is False
    assert row.change_allowed is True
    assert row.argmax_changed is True
    assert row.score_diff == pytest.approx(.0006)
    bad = replace(server, answers={"grade":{**server.answers["grade"], "score":2.01}})
    assert compare_request("score", questions, reference, bad, {"grade":tol}, 5e-5).status == "FAIL"


def test_unmeasured_and_atomic_failure(response_fixture):
    questions = response_fixture["questions"]
    valid = validate_response(json.dumps(response_fixture["valid"]), questions, 5e-5)
    result = compare_request("c", questions, valid, valid, {}, 5e-5)
    assert result.status == "INCOMPLETE" and result.n_expected == 3
    assert all(q.change_allowed is None for q in result.questions)
    broken = replace(valid, reason="score_value", answers=None)
    failed = compare_request("c", questions, valid, broken, {}, None)
    assert (failed.status, failed.n_compared, failed.n_failed) == ("FAIL", 0, 3)
    assert compare_request("c", questions, broken, valid, {}, None).status == "INCOMPLETE"
