"""무엇: 응답 단계·경고 검증 · 입력: 기존 응답 fixture/합성 경계 · 출력: Validated · 계약 §3-1."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from jeveval.contract.response import read_usage, validate_response
from jeveval.types import Request


ROOT = Path(__file__).parents[1] / "fixtures/responses"


def request():
    return Request("model", "원문", {"q": {"type": "noul"}})


def body():
    return {"answers": {"q": {"type": "noul", "noul": .7}}}


@pytest.mark.parametrize("path", sorted(ROOT.glob("*.json")), ids=lambda p: p.stem)
@pytest.mark.parametrize("as_bytes", [False, True])
def test_response_fixture(path, as_bytes):
    fixture = json.loads(path.read_text())
    req = Request("synthetic", "원문", fixture["request_questions"])
    before = deepcopy(req)
    raw = fixture["response_raw"]
    result = validate_response(raw.encode() if as_bytes else raw, req)
    expected = fixture["expected"]
    assert (result.reason is None) == expected["valid"]
    assert result.reason == expected["reason"]
    assert result.warnings == expected["warnings"]
    assert result.answers == (json.loads(raw)["answers"] if expected["valid"] else None)
    assert req == before


@pytest.mark.parametrize("raw", [b"\xff", "null", "[]", "{}", '{"answers":{"q":{',
    '{"answers":{},"provider":{"x":1,"x":2}}'])
def test_bad_body(raw):
    assert validate_response(raw, request()).reason == "bad_body"


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity", "1e999", "true"])
def test_nonfinite_and_bool_follow_field_reason(literal):
    raw = '{"answers":{"q":{"type":"noul","noul":' + literal + '}}}'
    assert validate_response(raw, request()).reason == "noul_value"


@pytest.mark.parametrize("usage,invalid", [(None, False), ({"input_tokens": 0}, False),
    ({"input_tokens": 12}, False), ({"input_tokens": True}, True), ({"input_tokens": 1.0}, True),
    ({"input_tokens": "1"}, True), ({}, True), ([], True), (1, True)])
def test_usage_warning_and_deduplication(usage, invalid):
    raw = body()
    raw.update(usage=usage, provider="synthetic")
    raw["answers"]["q"]["extra"] = "note"
    result = validate_response(json.dumps(raw), request())
    assert result.reason is None
    assert result.warnings == ["extra_keys"] + (["usage_input_tokens_invalid"] if invalid else [])


@pytest.mark.parametrize("failure", ["bad_body", "qid_mismatch", "type_mismatch", "noul_value"])
def test_warnings_survive_failure(failure):
    raw = body()
    raw.update(provider="synthetic", usage={"input_tokens": False})
    if failure == "bad_body":
        raw["answers"] = []
    elif failure == "qid_mismatch":
        raw["answers"] = {}
    elif failure == "type_mismatch":
        raw["answers"]["q"]["type"] = "choice"
    else:
        raw["answers"]["q"]["noul"] = -1
    result = validate_response(json.dumps(raw), request())
    assert result.reason == failure and result.answers is None
    assert result.warnings == ["extra_keys", "usage_input_tokens_invalid"]


def test_stages_are_global_and_choice_pick_is_last():
    req = Request("m", "s", {"first": {"type": "choice", "criteria": {"a": "a"}},
                             "second": {"type": "choice", "criteria": {"a": "a"}}})
    raw = {"answers": {"first": {"type": "choice", "probabilities": {"a": 0},
                               "choice": "missing", "confidence": 0},
                       "second": {"type": "choice", "probabilities": {}}}}
    assert validate_response(json.dumps(raw), req).reason == "choice_keys"
    raw["answers"]["second"]["probabilities"] = {"a": 1}
    assert validate_response(json.dumps(raw), req).reason == "choice_values"


@pytest.mark.parametrize("confidence", [None, True, "1", float("nan"), float("inf")])
def test_bad_choice_confidence(confidence):
    req = Request("m", "s", {"q": {"type": "choice", "criteria": {"a": "a"}}})
    raw = {"answers": {"q": dict(type="choice", probabilities={"a": 1}, choice="a", confidence=confidence)}}
    assert validate_response(json.dumps(raw), req).reason == "choice_pick"


@pytest.mark.parametrize("answer", [None, [], "noul", {}])
def test_malformed_answer_type(answer):
    assert validate_response(json.dumps({"answers": {"q": answer}}), request()).reason == "type_mismatch"


def test_score_request_stops_even_on_bad_json():
    with pytest.raises(NotImplementedError):
        validate_response("not json", Request("m", "s", {"q": {"type": "score"}}))


@pytest.mark.parametrize("usage,expected", [(None, (None, [])), ({"input_tokens": 12}, ({"input_tokens": 12}, [])),
    ({"input_tokens": 0}, ({"input_tokens": 0}, [])),
    ({"input_tokens": True}, (None, ["usage_input_tokens_invalid"])),
    ({"input_tokens": 1.0}, (None, ["usage_input_tokens_invalid"])),
    ({}, (None, ["usage_input_tokens_invalid"])), ([], (None, ["usage_input_tokens_invalid"]))])
def test_read_usage_independent_of_answers(usage, expected):
    raw = json.dumps({"error": "synthetic 422", "usage": usage})
    assert read_usage(raw) == read_usage(raw.encode()) == expected
    assert validate_response(raw, request()).reason == "bad_body"


@pytest.mark.parametrize("raw", ["{}", "null", "[]", "not json", b"\xff",
    '{"usage":{"input_tokens":1,"input_tokens":2}}'])
def test_read_usage_missing_or_unparseable(raw):
    assert read_usage(raw) == (None, [])


@pytest.mark.parametrize("confidence,warnings", [(1, []), (1 - 5e-10, []),
    (.99999999, ["confidence_differs"]), (0, ["confidence_differs"])])
def test_choice_confidence_difference(confidence, warnings):
    req = Request("m", "s", {"q": {"type": "choice", "criteria": {"a": "a"}}})
    raw = {"answers": {"q": dict(type="choice", probabilities={"a": 1}, choice="a", confidence=confidence)}}
    result = validate_response(json.dumps(raw), req)
    assert result.reason is None and result.warnings == warnings


@pytest.mark.parametrize("confidence", [-1e-10, 1 + 1e-10, -1, 1.2])
def test_choice_confidence_range(confidence):
    req = Request("m", "s", {"q": {"type": "choice", "criteria": {"a": "a", "b": "b"}}})
    raw = {"answers": {"q": dict(type="choice", probabilities={"a": 0, "b": 1},
                                 choice="a" if confidence < 0 else "b", confidence=confidence)}}
    result = validate_response(json.dumps(raw), req)
    assert result.reason == "choice_pick" and result.warnings == []


@pytest.mark.parametrize("invalid", [False, True])
def test_confidence_warning_order_and_atomicity(invalid):
    req = Request("m", "s", {"c": {"type": "choice", "criteria": {"a": "a"}}, "n": {"type": "noul"}})
    raw = {"answers": {"c": dict(type="choice", probabilities={"a": 1}, choice="a", confidence=.2),
                       "n": dict(type="noul", noul=-1 if invalid else .9)}, "usage": {"input_tokens": True}}
    result = validate_response(json.dumps(raw), req)
    assert result.reason == ("noul_value" if invalid else None)
    assert result.warnings == ["extra_keys", "usage_input_tokens_invalid"] + ([] if invalid else ["confidence_differs"])
