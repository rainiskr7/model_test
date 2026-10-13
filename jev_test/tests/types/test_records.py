"""무엇: 요청·중첩 기록 JSON 왕복 · 입력: 합성 기록 · 출력: 검증 · 계약 §2·§5-3."""

from dataclasses import FrozenInstanceError
import json

import pytest

from jeveval.types import AttemptRecord, CallRecord, FinalRecord, Request


def call():
    return CallRecord("s:g:i", 2, "ok", None, "a" * 64, 12, 7,
                      {"input_tokens": 12}, {"ready": {"type": "noul", "noul": .8}},
                      {"A": "true", "B": "false"}, [{"token": "A", "logprob": -.2}])


@pytest.mark.parametrize("record", [
    Request("synthetic", "짧은 입력", {"ready": {"type": "noul", "criteria": {
        "true": "준비됨", "false": "준비 안 됨"}}}),
    AttemptRecord("s:g:i", "s:g:i", 1, "start", "end", 1.5, 200, None, None,
                  True, "a" * 64, '{"answers":{}}'),
    AttemptRecord("s:g:i", "s:g:i", 2, "start", "end", 2, None, "1", "timeout",
                  False, "a" * 64, {"b64": "/w=="}),
    AttemptRecord("s:g:i", "s:g:i", 3, "start", "end", 2, 503, 1.0, None,
                  True, "a" * 64, "{}"),
    call(),
    FinalRecord("s:g:i", "ok", None, False, [], [call()]),
    FinalRecord("s:g:i", "error", "transport", False, ["extra_keys"], [], "full/run"),
])
def test_record_roundtrip(record):
    restored = type(record).from_dict(json.loads(json.dumps(record.to_dict())))
    assert restored == record
    with pytest.raises(FrozenInstanceError):
        record.logical_id = "changed"


def test_nested_types_rebuilt():
    original = FinalRecord("s:g:i", "ok", None, False, [], [call()])
    restored = FinalRecord.from_dict(original.to_dict())
    assert isinstance(restored.calls[0], CallRecord)
    assert restored.calls[0].answers_parsed == original.calls[0].answers_parsed
    assert restored.calls[0].answers_parsed is not original.calls[0].answers_parsed


def test_omitted_optional_fields():
    data = call().to_dict()
    del data["label_map"], data["top_logprobs_raw"]
    restored = CallRecord.from_dict(data)
    assert restored.label_map is None
    assert restored.top_logprobs_raw is None


def test_envelope_field_names():
    assert set(Request("m", "s", {}).to_dict()) == {"model", "state", "questions"}
