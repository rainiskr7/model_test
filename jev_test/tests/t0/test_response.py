"""무엇: T0 검증 fixture/기존 계약 동등성 · 입력: 정상/오류 JSON · 출력: 사유/전부 거부 · 계약 T-b/c."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from jeveval.contract.response import validate_response as standard
from jeveval.t0.response import validate_response
from jeveval.types import Request

ROOT = Path(__file__).parents[1] / "fixtures"
FIXTURE = json.loads((ROOT / "t0/responses.json").read_text())


@pytest.mark.parametrize("case", FIXTURE["cases"], ids=lambda c: c["id"])
def test_score_and_mixed_errors(response_fixture, case):
    body = response_fixture["valid"]
    for qid, key, value in case["changes"]:
        body["answers"][qid][key] = value
    if "remove" in case:
        qid, key = case["remove"]
        del body["answers"][qid][key]
    result = validate_response(json.dumps(body), response_fixture["questions"], 5e-5)
    assert result.reason == case["reason"]
    assert result.answers == (body["answers"] if case["reason"] is None else None)


@pytest.mark.parametrize("case", FIXTURE["raw_cases"], ids=lambda c: c["id"])
def test_nonfinite_and_duplicate_raw(response_fixture, case):
    raw = case.get("raw")
    if raw is None:
        raw = json.dumps(response_fixture["valid"]).replace("1.9997", case["replace"])
    assert validate_response(raw, response_fixture["questions"], 5e-5).reason == case["reason"]


@pytest.mark.parametrize("path", sorted((ROOT / "responses").glob("*.json")), ids=lambda p: p.stem)
def test_original_response_fixtures_unchanged(path):
    data = json.loads(path.read_text())
    questions = data["request_questions"]
    expected = standard(data["response_raw"], Request("m", "s", questions))
    for epsilon in (0, 5e-5):
        assert validate_response(data["response_raw"].encode(), questions, epsilon) == expected


def test_unknown_rounding_and_request_atomicity(response_fixture):
    body, questions = response_fixture["valid"], response_fixture["questions"]
    before = deepcopy(body)
    assert validate_response(json.dumps(body), questions, None).reason == "unknown_rounding"
    assert validate_response(json.dumps(body), questions, 0).reason == "score_value"
    body["answers"]["grade"]["legend"]["0"] = "wrong"
    result = validate_response(json.dumps(body), questions, None)
    assert result.reason == "score_legend" and result.answers is None
    assert before["answers"]["binary"] == body["answers"]["binary"]


def test_envelope_warnings_before_bad_answers():
    raw = '{"provider":"x","usage":{"input_tokens":true},"answers":[]}'
    questions = {"q":{"type":"noul"}}
    assert validate_response(raw, questions, 0) == standard(raw, Request("m", "s", questions))


@pytest.mark.parametrize("epsilon", [-1, True, float("nan"), float("inf")])
def test_bad_rounding_parameter(response_fixture, epsilon):
    with pytest.raises(ValueError):
        validate_response(json.dumps(response_fixture["valid"]), response_fixture["questions"], epsilon)


@pytest.mark.parametrize("invalid", [False, True])
def test_confidence_warnings_only_on_valid_request(response_fixture, invalid):
    body, questions = response_fixture["valid"], response_fixture["questions"]
    for qid, question in questions.items():
        if question["type"] == "choice":
            body["answers"][qid]["confidence"] = .123
    body["usage"] = {"input_tokens": True}
    if invalid:
        body["answers"]["grade"]["legend"]["0"] = "wrong"
    result = validate_response(json.dumps(body), questions, 5e-5)
    assert result.warnings == ["extra_keys", "usage_input_tokens_invalid"] + ([] if invalid else ["confidence_differs"])
    assert bool(result.reason) == invalid


def test_reasons_unchanged():
    from jeveval.t0.response import REASONS
    assert REASONS == ("type_mismatch", "noul_value", "choice_keys", "choice_values", "choice_pick",
                       "score_keys", "score_values", "score_legend", "score_confidence", "score_value", "unknown_rounding")


@pytest.mark.parametrize("noul", [-1, .8])
def test_multi_question_warning_equality(noul):
    questions = {"c": {"type": "choice", "criteria": {"a": "a"}}, "n": {"type": "noul"}}
    raw = json.dumps({"answers": {"c": dict(type="choice", choice="a", confidence=.2,
                                            probabilities={"a": 1}), "n": dict(type="noul", noul=noul)}})
    assert validate_response(raw, questions, 0) == standard(raw, Request("m", "s", questions))
