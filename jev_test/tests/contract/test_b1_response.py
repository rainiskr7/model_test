"""무엇: B1 응답·기록 경계 · 입력: 합성 raw · 출력: 검증·채점·복구 일치 · 계약 §3-2·§5-5b."""

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import pytest

from jeveval.client.attempt import to_attempt_record
from jeveval.contract.b1_response import read_b1_response, storable_top_logprobs
from jeveval.io.records import append_record, read_attempts, read_finals
from jeveval.score.answers import parse_b1
from jeveval.types import AttemptResult, B1Response, FinalRecord


def body(logprob=-2):
    return {"choices": [{"logprobs": {"content": [{"top_logprobs": [
        {"token": " A", "logprob": -1}, {"token": "B", "logprob": logprob}]}]}}],
        "usage": {"prompt_tokens": 12}}


def test_normal_response_flows_to_parser_and_roundtrips():
    result = read_b1_response(json.dumps(body()).encode())
    assert result.reason is None and result.warnings == []
    assert result.usage == {"input_tokens": 12}
    assert all(type(row["logprob"]) is float for row in result.top_logprobs)
    answer = parse_b1(result.top_logprobs, ["A", "B"], {"A": "true", "B": "false"}, "noul")
    assert answer.reason is None and answer.parsed.answer == "true"
    assert B1Response.from_dict(result.to_dict()) == result


@pytest.mark.parametrize("value", [True, None, "-1", float("nan"), float("inf"), .1, 10**400, -(10**400)])
def test_bad_logprob_keeps_usage(value):
    result = read_b1_response(json.dumps(body(value)))
    assert result.reason == "bad_body" and result.top_logprobs is None
    assert result.usage == {"input_tokens": 12}


@pytest.mark.parametrize("choices", [None, [], {}, "x", [None], [{}], [{"logprobs": None}],
    [{"logprobs": {"content": []}}], [{"logprobs": {"content": [{"top_logprobs": {}}]}}],
    [{"logprobs": {"content": [{"top_logprobs": [None]}]}}],
    [{"logprobs": {"content": [{"top_logprobs": [{"token": 1, "logprob": -1}]}]}}]])
def test_bad_structure_keeps_usage(choices):
    result = read_b1_response(json.dumps({"choices": choices, "usage": {"prompt_tokens": 0}}))
    assert (result.reason, result.usage) == ("bad_body", {"input_tokens": 0})


@pytest.mark.parametrize("raw", [b"\xff", "null", "[]", "bad json", '{"usage":{},"usage":{}}',
    '{"extra":{"x":1,"x":2}}'])
def test_bad_json_and_duplicate_keys(raw):
    assert read_b1_response(raw) == B1Response("bad_body", [], None, None)


@pytest.mark.parametrize("usage,expected,warning", [(None, None, False), ({}, None, True),
    ([], None, True), ({"prompt_tokens": True}, None, True), ({"prompt_tokens": 1.0}, None, True),
    ({"prompt_tokens": "12"}, None, True), ({"prompt_tokens": 12}, {"input_tokens": 12}, False)])
def test_usage_independent_of_missing_choices(usage, expected, warning):
    result = read_b1_response(json.dumps({"usage": usage}))
    assert result.reason == "bad_body" and result.usage == expected
    assert result.warnings == (["usage_input_tokens_invalid"] if warning else [])


def test_missing_usage_and_empty_top_logprobs():
    raw = body()
    del raw["usage"]
    raw["choices"][0]["logprobs"]["content"][0]["top_logprobs"] = []
    result = read_b1_response(json.dumps(raw))
    assert (result.reason, result.usage, result.warnings, result.top_logprobs) == (None, None, [], [])
    assert parse_b1(result.top_logprobs, ["A"], {"A": "x"}, "choice").reason == "b1_missing_label"


def test_nonfinite_storage_is_detached_and_type_roundtrip_safe():
    response = read_b1_response(json.dumps(body(float("-inf"))))
    before = deepcopy(response)
    rows = storable_top_logprobs(response.top_logprobs)
    assert rows[1]["logprob"] == "-inf"
    json.dumps(rows, allow_nan=False)
    assert B1Response.from_dict(response.to_dict()) == response
    rows[0]["token"] = "changed"
    assert response == before


@pytest.mark.parametrize("logprob", [-2, float("-inf")])
def test_terminal_attempt_rebuilds_identical_storable_final(tmp_path, logprob):
    raw = json.dumps(body(logprob))
    result = AttemptResult("start", "end", 1.0, 200, None, None, raw)
    attempt = to_attempt_record(result, call_id="synthetic:g:b1_partial/ready",
        logical_id="synthetic:g:b1_partial", attempt=1, session_id="session", terminal=True,
        request_sha256="a" * 64)
    fixture = json.loads((Path(__file__).parents[1] / "fixtures/records/roundtrip.json").read_text())
    template = FinalRecord.from_dict(fixture["cases"][-1]["record"])

    def rebuild(raw):
        response = read_b1_response(raw)
        parsed = parse_b1(response.top_logprobs, ["A", "B"], {"A": "true", "B": "false"}, "noul")
        status = "error" if parsed.reason else "ok"
        call = replace(template.calls[0], status=status, reason=parsed.reason, usage=response.usage,
            answers_parsed={"ready": parsed.parsed} if parsed.parsed else None,
            top_logprobs_raw=storable_top_logprobs(response.top_logprobs))
        return replace(template, status=status, reason=parsed.reason, calls=[call])

    first = rebuild(raw)
    append_record(tmp_path / "attempts", attempt)
    restored, warnings = read_attempts(tmp_path / "attempts")
    assert warnings == [] and restored[0].terminal
    recovered = rebuild(restored[0].response_raw)
    assert recovered == first
    append_record(tmp_path / "final", recovered)
    assert read_finals(tmp_path / "final") == ([first], [])
