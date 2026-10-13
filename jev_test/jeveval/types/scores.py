"""무엇: 임계값·위험·집계 자료형 · 입력: JSON 필드 · 출력: dataclass · 계약 §7-4~7-6."""

from dataclasses import dataclass

from .base import JsonRecord


@dataclass(frozen=True)
class Threshold(JsonRecord):
    tau: str
    status: str
    t_star: float | None
    n_accepted: int | None
    k_errors: int | None
    coverage: dict


@dataclass(frozen=True)
class ThresholdFile(JsonRecord):
    schema: str
    model: str
    set: str
    variant: str
    run_id: str
    rule: str
    unit: str
    dev_input: dict
    by_tau: dict[str, Threshold]

    def __post_init__(self):
        if any(key != value.tau for key, value in self.by_tau.items()):
            raise ValueError("by_tau key must equal value.tau")


@dataclass(frozen=True)
class RiskCell(JsonRecord):
    tau: str
    status: str
    insufficient_by_design: bool
    unit: str
    t_star: float | None
    dev: dict
    test: dict
    by_status: dict
    accepted_mix: dict
    by_length_bucket: dict
    diagnostic_error_in_accepted: dict


@dataclass(frozen=True)
class QStats(JsonRecord):
    role: str
    type: str
    n_scored: int
    n_missing: int
    accuracy: dict
    macro_f1: float | None
    classes: dict
    calibration: dict
    warnings: dict


@dataclass(frozen=True)
class Population(JsonRecord):
    certified: bool
    unit: str
    counts: dict
    request: dict
    questions: dict[str, QStats]
    pooled: dict[str, QStats]
    set_specific: dict


@dataclass(frozen=True)
class Cost(JsonRecord):
    n_logical: int
    n_calls: int
    n_attempts: int
    n_retries: int
    failure: dict
    latency_ms: dict
    input_tokens: dict
    derived_from: str | None


@dataclass(frozen=True)
class ScoreTable(JsonRecord):
    schema: str
    model: str
    set: str
    variant: str
    run_id: str
    populations: dict[str, Population]
    cost: dict
