"""무엇: 항목·설정·분할 타입 · 입력: JSON 필드 · 출력: dataclass · 계약 §1·§6."""

from dataclasses import dataclass
from typing import Any

from . import JsonRecord


@dataclass(frozen=True)
class Item(JsonRecord):
    """§6에 명시된 식별 필드만. 항목 본문·정답 필드는 SPEC_AMBIGUOUS."""

    set: str
    group_id: str | int
    item_id: str | int


@dataclass(frozen=True)
class QuestionSpec(JsonRecord):
    id: str
    role: str
    type: str
    instructions: str
    label: str
    options: str | None = None
    criteria: dict[str, str] | None = None


@dataclass(frozen=True)
class TaskSpec(JsonRecord):
    set: str
    variant: str
    state: dict[str, Any]
    questions: list[QuestionSpec]
    per_item_questions: dict[str, Any] | None
    group_key: str


@dataclass(frozen=True)
class SplitPlan(JsonRecord):
    set: str
    seed: int
    pool_rule: Any
    allocation: dict[str, int]
    groups: dict[str, list[str | int]]
    representative: dict[str, str]
    dev: list[str]
    test: list[str]
    diagnostic_demotions: list[str]
