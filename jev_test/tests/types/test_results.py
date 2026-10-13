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
