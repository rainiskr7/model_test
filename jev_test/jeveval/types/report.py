"""무엇: 공개 보고서 중간 표현 · 입력: 검증된 통계 · 출력: frozen dataclass · 계약 §7-6."""

from dataclasses import dataclass, field

from .history import StageCheck


@dataclass(frozen=True)
class ReportQuestion:
    question_id: str
    role: str
    numerator: int
    denominator: int
    macro_f1: float | None
    ece: float | None
    support: int | None
    predicted: int | None
    tp: int | None
    sparse: bool


@dataclass(frozen=True)
class ReportRisk:
    tau: str
    status: str
    accepted: int | None
    denominator: int
    errors: int | None
    upper: float | None
    insufficient: bool


@dataclass(frozen=True)
class ReplayOrigin:
    stage: str
    source_run_id: str
    source_code_sha256: str
    source_attempts_sha256: str


@dataclass(frozen=True)
class KosgdDecomposition:
    stage: str
    correct: int
    slots_only: int
    actions_only: int
    both: int
    errors: dict[str, int]
    grid: list[list[int]]
    duplicate_unique_match: int
    valid_ids: list[str]
    wrong_ids: list[str]


@dataclass(frozen=True)
class CommonErrors:
    left: str
    right: str
    set_name: str
    variant: str
    stage: str
    common: int
    excluded_left: int
    excluded_right: int
    both_wrong: int


@dataclass(frozen=True)
class ReportComparison:
    compare_id: str
    set_name: str
    variant: str
    lines: list[str]


@dataclass(frozen=True)
class ReportVariant:
    model: str
    set_name: str
    variant: str
    status: str
    reasons: list[str]
    stages: list[StageCheck]
    code_sha256: str | None = None
    started_at: str | None = None
    primary: bool | None = None
    t0_status: str = "unknown"
    replay: list[ReplayOrigin] = field(default_factory=list)
    risk: list[ReportRisk] = field(default_factory=list)
    questions: list[ReportQuestion] = field(default_factory=list)
    decompositions: list[KosgdDecomposition] = field(default_factory=list)
    supplementary: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Report:
    run_id: str
    models: list[str]
    variants: list[ReportVariant]
    comparisons: list[ReportComparison]
    common_errors: list[CommonErrors]
    unrun: list[str]
