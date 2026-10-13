"""무엇: 메모리 전용 요청 채점 결과 · 입력: 요청별 값 · 출력: dataclass · 계약 §7-8·§8-5."""

from dataclasses import dataclass

from .base import JsonRecord


@dataclass(frozen=True)
class RequestOutcome(JsonRecord):
    logical_id: str
    group_id: str
    stage: str
    status: str
    valid: bool
    mask_empty: bool
    s: float | None
    wrong: bool | None
    gold: dict[str, str | None]
    answer: dict[str, str] | None
    length_max: int | None
    meta: dict
