"""무엇: 렌더·응답·길이 자료형 · 입력: JSON 필드 · 출력: dataclass · 계약 §2-2·§3-2·§4-3."""

from dataclasses import dataclass

from .base import JsonRecord


@dataclass(frozen=True)
class Rendered(JsonRecord):
    state: str
    target_end_char: int


@dataclass(frozen=True)
class ParsedAnswer(JsonRecord):
    type: str
    answer: str
    probs: dict[str, float]
    confidence: float


@dataclass(frozen=True)
class LengthInfo(JsonRecord):
    length_tokens: int
    target_end: int
    limit: int
    fixed_tokens: int
    usage_tokens: int | None = None  # 서버 usage.input_tokens 와 비교할 기대값 — None 이면 length_tokens (pplx 는 질문 행 길이의 합)
