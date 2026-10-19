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
    roles: dict[str, str]

    def __post_init__(self):
        """모든 질문의 역할을 보존한다. gold는 MISSING도 키를 가진다 (§8-6 D)."""
        if not isinstance(self.roles, dict):
            raise TypeError("roles: expected object")
        if self.roles.keys() != self.gold.keys():
            raise ValueError("roles: expected all question IDs")
        if any(not isinstance(key, str) or role not in ("success", "diagnostic")
               for key, role in self.roles.items()):
            raise ValueError("roles: expected success or diagnostic")


@dataclass(frozen=True)
class QuestionOutcome(JsonRecord):
    """질문 하나 또는 두 칸 묶음의 관측. 무효성은 논리 요청에서 상속한다."""

    logical_id: str
    group_id: str
    stage: str
    status: str
    valid: bool
    question_id: str
    role: str
    label: str
    qtype: str
    gold: str | None
    answer: str | None
    confidence: float | None
    wrong: bool | None
    present: bool
    length_max: int | None
    meta: dict
