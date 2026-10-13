"""무엇: 기록 중첩 타입 경계 · 입력: 합성 JSON · 출력: 검증 · 계약 §5-3·§8-5."""

from dataclasses import replace

import pytest

from jeveval.types import AttemptRecord, CallRecord, FinalRecord, LengthInfo, ParsedAnswer, Request
from samples import attempt, call


def test_nested_types_rebuilt():
    original = FinalRecord(logical_id='s:g:i',status='ok',reason=None,answered_over_limit=False,warnings=[],calls=[call()])
    source = original.to_dict()
    restored = FinalRecord.from_dict(source)
    assert isinstance(restored.calls[0], CallRecord)
    assert isinstance(restored.calls[0].length, LengthInfo)
    assert isinstance(restored.calls[0].answers_parsed['ready'], ParsedAnswer)
    source['calls'][0]['answers_parsed']['ready']['probs']['true'] = 0
    assert restored == original
    assert restored.calls[0].answers_parsed is not original.calls[0].answers_parsed


def test_omitted_optional_fields():
    data = call().to_dict()
    del data['label_map'],data['top_logprobs_raw']
    restored = CallRecord.from_dict(data)
    assert restored.label_map is restored.top_logprobs_raw is None


@pytest.mark.parametrize('record', [attempt(),replace(attempt(),response_raw={'b64':'/w=='},http_status=None),
    replace(attempt(),retry_after=1.0),replace(attempt(),retry_after='1'),
    replace(call(),status='error',reason='request_contract',length=None,answers_parsed=None)])
def test_record_variants(record):
    assert type(record).from_dict(record.to_dict()) == record


def test_session_id_required():
    data = attempt().to_dict()
    del data['session_id']
    with pytest.raises(TypeError):
        AttemptRecord.from_dict(data)


def test_envelope_field_names():
    assert set(Request(model='m',state='s',questions={}).to_dict()) == {'model','state','questions'}
