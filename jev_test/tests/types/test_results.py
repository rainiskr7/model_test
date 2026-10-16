"""무엇: 응답·길이 자료형 경계 · 입력: 합성 JSON · 출력: 검증 · 계약 §3·§4·§8-5."""

import pytest

from jeveval.types import LengthInfo, ParsedAnswer, Rendered


@pytest.mark.parametrize('record', [
    ParsedAnswer(type='noul',answer='true',probs={'true':.5,'false':.5},confidence=.5),
    ParsedAnswer(type='choice',answer='B',probs={'A':.5,'B':.5},confidence=.5),
    LengthInfo(length_tokens=100,target_end=80,limit=100,fixed_tokens=20),
    Rendered(state='한글',target_end_char=2),
])
def test_result_roundtrip(record):
    assert type(record).from_dict(record.to_dict()) == record


@pytest.mark.parametrize('value', [float('nan'),float('inf'),-float('inf')])
def test_non_json_numbers_rejected(value):
    with pytest.raises(ValueError):
        ParsedAnswer(type='noul',answer='true',probs={'true':value},confidence=.5).to_dict()
    with pytest.raises(ValueError):
        ParsedAnswer.from_dict(dict(type='noul',answer='true',probs={'true':value},confidence=.5))


def test_parsed_answer_uses_strings_and_detaches_probabilities():
    source = dict(type='noul',answer='true',probs={'true':.5,'false':.5},confidence=.5)
    restored = ParsedAnswer.from_dict(source)
    source['probs']['true'] = 0
    assert restored.probs['true'] == .5
    source['answer'] = True
    with pytest.raises(TypeError):
        ParsedAnswer.from_dict(source)


def test_length_usage_default_and_legacy_dict_restoration():
    old = dict(length_tokens=14, target_end=2, limit=100, fixed_tokens=11)
    value = LengthInfo(**old)
    assert value.usage_tokens is None
    assert LengthInfo.from_dict(old) == value
    assert value.to_dict() == {**old, "usage_tokens": None}


@pytest.mark.parametrize("usage", [None, 0, 26])
def test_length_usage_tokens_roundtrip(usage):
    value = LengthInfo(14, 2, 100, 11, usage_tokens=usage)
    assert value.to_dict()["usage_tokens"] == usage
    assert LengthInfo.from_dict(value.to_dict()) == value
