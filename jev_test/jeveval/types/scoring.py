"""무엇: 답 파싱·채점 결과 타입 · 입력: 계산 결과 · 출력: JSON 왕복 · 계약 §8-5."""

from dataclasses import dataclass

from .base import JsonRecord
from .results import ParsedAnswer


@dataclass(frozen=True)
class AnswerParse(JsonRecord):
    parsed: ParsedAnswer | None
    reason: str | None
    warnings: list[str]
    label_probs: dict[str, float] | None


@dataclass(frozen=True)
class F1Result(JsonRecord):
    classes: list[str]
    per_class_f1: dict[str, float]
    macro_f1: float | None
    class_stats: dict


@dataclass(frozen=True)
class CalibResult(JsonRecord):
    ece: float | None
    bins: list[dict]
    brier: float | None
    log_loss: float | None


@dataclass(frozen=True)
class SlotJudgement(JsonRecord):
    fixed_gold: list[str]
    group_correct: bool
    duplicate_non_none: bool
    order_only: bool
