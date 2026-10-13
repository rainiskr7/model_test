"""무엇: 응답 검증·B1 호출 타입 · 입력: 계약 필드 · 출력: JSON 왕복 · 계약 §8-5."""

from dataclasses import dataclass

from .base import JsonRecord


@dataclass(frozen=True)
class Validated(JsonRecord):
    reason: str | None
    warnings: list[str]
    answers: dict[str, dict] | None


@dataclass(frozen=True)
class B1Config(JsonRecord):
    system: str
    labels: list[str]
    params: dict


@dataclass(frozen=True)
class B1Call(JsonRecord):
    call_qid: str
    messages: list[dict]
    label_order: list[str]
    label_map: dict[str, str]
    params: dict
