"""무엇: 공통 JSON 왕복 · 입력: dataclass/JSON 객체 · 출력: 사본 · 계약 §8-1."""

from dataclasses import asdict, fields, is_dataclass
import json
from types import UnionType
from typing import Any, Union, get_args, get_origin, get_type_hints


def _decode(hint, value):
    """JSON 컨테이너 안의 dataclass까지 복원한다."""
    origin, args = get_origin(hint), get_args(hint)
    if origin in (Union, UnionType):
        if value is None and type(None) in args:
            return None
        candidates = [arg for arg in args if arg is not type(None)]
        for candidate in candidates:
            try:
                return _decode(candidate, value)
            except (TypeError, ValueError):
                pass
        raise TypeError(f"{hint}: {value!r}")
    if is_dataclass(hint):
        return hint.from_dict(value)
    if origin is list:
        if not isinstance(value, list):
            raise TypeError("expected list")
        return [_decode(args[0], item) for item in value]
    if origin is dict:
        if not isinstance(value, dict):
            raise TypeError("expected object")
        return {_decode(args[0], k): _decode(args[1], v)
                for k, v in value.items()}
    if hint is not Any:
        valid = type(value) is hint
        if hint is float:
            valid = type(value) in (int, float)
        if not valid:
            raise TypeError(f"expected {hint}")
    return value


class JsonRecord:
    """실제 JSON을 거쳐 별칭 없는 사본을 만든다. 도메인 검증은 contract 담당."""

    def to_dict(self) -> dict:
        return json.loads(json.dumps(asdict(self), ensure_ascii=False,
                                     allow_nan=False))

    @classmethod
    def from_dict(cls, value: dict):
        if not isinstance(value, dict):
            raise TypeError("expected JSON object")
        data = json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))
        names = {field.name for field in fields(cls)}
        unknown = data.keys() - names
        if unknown:
            raise ValueError(f"unknown fields: {sorted(unknown)}")
        hints = get_type_hints(cls)
        return cls(**{key: _decode(hints[key], val) for key, val in data.items()})
