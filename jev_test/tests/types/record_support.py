"""자료형 짝 시험에서 공유하는 JSON/메모리 경계 검사."""

from dataclasses import FrozenInstanceError, MISSING, fields
import json

import pytest

from jeveval.types import JsonRecord


def check_record(record):
    payload = json.loads(json.dumps(record.to_dict(), ensure_ascii=False, allow_nan=False))
    restored = type(record).from_dict(payload)
    assert isinstance(restored, JsonRecord) and restored == record
    first = fields(record)[0].name
    with pytest.raises(FrozenInstanceError):
        setattr(record, first, None)
    for field in fields(record):
        if field.default is MISSING and field.default_factory is MISSING:
            missing = dict(payload)
            del missing[field.name]
            with pytest.raises(TypeError):
                type(record).from_dict(missing)
    payload.clear()
    assert restored == record


def check_memory_record(record):
    assert not isinstance(record, JsonRecord)
    values = {field.name: getattr(record, field.name) for field in fields(record)}
    assert type(record)(**values) == record
    with pytest.raises(FrozenInstanceError):
        setattr(record, next(iter(values)), None)
    for field in fields(record):
        if field.default is MISSING and field.default_factory is MISSING:
            missing = dict(values)
            del missing[field.name]
            with pytest.raises(TypeError):
                type(record)(**missing)
