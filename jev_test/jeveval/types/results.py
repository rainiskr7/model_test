"""무엇: 응답·길이·위험 타입 · 입력: JSON 필드 · 출력: dataclass · 계약 §3·§5-3·§7-4."""

from dataclasses import dataclass
from typing import Any

from . import JsonRecord


@dataclass(frozen=True)
class ParsedAnswer(JsonRecord):
    """§3의 명시된 응답 필드만. 파싱 후 별도 스키마는 SPEC_AMBIGUOUS."""

    type: str
    noul: float | None = None
    choice: str | None = None
    confidence: float | None = None
    probabilities: dict[str, float] | None = None


@dataclass(frozen=True)
class LengthInfo(JsonRecord):
    """§5-3의 기록 필드만. 고정부·상한의 필드명은 SPEC_AMBIGUOUS."""

    length_tokens: int
    target_end: int


@dataclass(frozen=True)
class Threshold(JsonRecord):
    """§7-4의 단일 t_star. threshold.json 전체 구조는 SPEC_AMBIGUOUS."""

    t_star: float | None


@dataclass(frozen=True)
class RiskCell(JsonRecord):
    status: str
    insufficient_by_design: bool
    t_star: float | None
    dev: dict[str, Any]
    test: dict[str, Any]
    by_status: dict[str, int]
    accepted_mix: dict[str, Any]
    diagnostic_error_in_accepted: dict[str, dict[str, int]]


@dataclass(frozen=True)
class ScoreTable(JsonRecord):
    """필드 미정(§8-1·§8-3). 빈 스키마만 왕복하며 실제 점수 입력은 거부한다."""
