"""무엇: 공통 JSON 왕복 경계 · 입력: 모든 자료형 표본 · 출력: 검증 · 계약 §8-5."""

from dataclasses import MISSING, FrozenInstanceError, fields
import json
from types import NoneType
from typing import Any, get_args, get_type_hints

import pytest

from samples import records


@pytest.mark.parametrize('record', records(), ids=lambda x:type(x).__name__)
def test_roundtrip_and_frozen(record):
    restored = type(record).from_dict(json.loads(json.dumps(record.to_dict())))
    assert restored == record
    with pytest.raises(FrozenInstanceError):
        record.guessed_field = 1


@pytest.mark.parametrize('record', records(), ids=lambda x:type(x).__name__)
def test_nullability_and_required_fields(record):
    hints = get_type_hints(type(record))
    for field in fields(record):
        if field.default is MISSING and field.default_factory is MISSING:
            missing = record.to_dict()
            del missing[field.name]
            with pytest.raises(TypeError):
                type(record).from_dict(missing)
        hint = hints[field.name]
        data = record.to_dict()
        data[field.name] = None
        if hint is Any or NoneType in get_args(hint):
            assert getattr(type(record).from_dict(data),field.name) is None
        else:
            with pytest.raises(TypeError):
                type(record).from_dict(data)


@pytest.mark.parametrize('record', records(), ids=lambda x:type(x).__name__)
def test_unknown_fields_and_detached_containers(record):
    data = record.to_dict()
    data['invented'] = 1
    with pytest.raises(ValueError,match='unknown fields'):
        type(record).from_dict(data)
    source = record.to_dict()
    restored = type(record).from_dict(source)
    source.clear()
    assert restored == record
