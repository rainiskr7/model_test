"""무엇: 항목·설정·분할 타입 · 입력: JSON 필드 · 출력: dataclass · 계약 §1·§6."""

from dataclasses import dataclass
from typing import Any

from .base import JsonRecord


@dataclass(frozen=True)
class SourceRow(JsonRecord):
    set: str
    row_id: str
    fields: dict


@dataclass(frozen=True)
class BoundQuestion(JsonRecord):
    id: str
    role: str
    type: str
    instructions: str
    options: dict[str, str] | None
    criteria: dict[str, str] | None
    label: str
    gold: str | None


@dataclass(frozen=True)
class ItemFields:
    """조립 전 내부 필드. Item의 JSON 구조에 중첩하지 않는다 (§6-2)."""

    state_fields: dict | str
    questions: list[BoundQuestion]
    meta: dict
    baseline: dict | None


@dataclass(frozen=True)
class Item(JsonRecord):
    set: str
    group_id: str
    item_id: str
    state_fields: dict | str
    questions: list[BoundQuestion]
    meta: dict
    baseline: dict | None


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
    groups: dict[str, list[str]]
    representative: dict[str, str]
    dev: list[str]
    test: list[str]
    diagnostic_demotions: list[str]
    extra: list[str]
    notes: dict


@dataclass(frozen=True)
class Groups(JsonRecord):
    """전체 원본 행의 묶음 연결과 항목 구성원 (§6 보정 6)."""

    row_to_group: dict[str, str]
    members: dict[str, list[str]]


@dataclass(frozen=True)
class PoolResult(JsonRecord):
    """선정된 평가 풀 묶음과 층별 할당 (§6 보정 6)."""

    group_ids: list[str]
    allocation: dict[str, int]
