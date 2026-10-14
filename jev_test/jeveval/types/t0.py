"""무엇: T0 순수 층 자료형 · 입력: 요청/관측/판정 · 출력: dataclass · 계약 §8-7."""

from dataclasses import dataclass, field

from .base import JsonRecord
from .contract import Validated


@dataclass(frozen=True)
class T0Request:
    body: dict
    envelope_bytes: bytes
    envelope_sha256: str
    request_sha256: str
    target_end_char: int


@dataclass(frozen=True)
class T0Variant:
    variant: str
    repeat: int
    target_sha256: dict[str, str]
    response: Validated


@dataclass(frozen=True)
class T0Tolerance(JsonRecord):
    measurement: str
    status: str
    variation: float | None
    tol_prob: float | None
    variants: list[str]
    repeats: int
    reason: str | None = None


@dataclass(frozen=True)
class T0QuestionComparison(JsonRecord):
    question_id: str
    status: str
    max_abs_diff: float
    answer_changed: bool
    change_allowed: bool | None
    distribution_ok: bool | None
    score_diff: float | None = None
    argmax_changed: bool | None = None


@dataclass(frozen=True)
class T0CaseResult(JsonRecord):
    case_id: str
    status: str
    n_expected: int
    n_compared: int
    n_failed: int
    questions: list[T0QuestionComparison] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    boundary: bool = False


@dataclass(frozen=True)
class T0Boundary(JsonRecord):
    lengths: list[int] | None
    limit: int
    overflow: str
    input_limit_response: dict | None = None


@dataclass(frozen=True)
class T0Case:
    case_id: str
    request: T0Request
    reference_envelope_sha256: str
    boundary: T0Boundary | None = None


@dataclass(frozen=True)
class T0Observation(JsonRecord):
    case_id: str
    inputs_sha256: str
    request_sha256: str
    envelope_sha256: str
    http_status: int | None
    response_raw: str
    transport_error: str | None = None
    length_status: str | None = None


@dataclass(frozen=True)
class T0Judgement(JsonRecord):
    status: str
    n_expected_cases: int
    n_expected_questions: int
    n_compared: int
    n_failed: int
    n_changed: int
    n_allowed: int
    n_violated: int
    max_abs_diff: float | None
    cases: list[T0CaseResult]
