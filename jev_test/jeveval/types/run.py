"""무엇: 실행 공유 타입 · 입력: 설정·호출 계획·집계 · 출력: dataclass · 계약 §8-5·§8-6."""

from dataclasses import dataclass

from .base import JsonRecord
from .contract import B1Call
from .records import Request
from .results import Rendered


@dataclass(frozen=True)
class ModelConfig(JsonRecord):
    id: str
    kind: str
    served_name: str | None
    base_url: str | None
    auth_env: str | None
    question_scoring: str
    limit: dict
    input_limit_response: dict | None
    encoder: dict
    tokenizer: dict
    concurrency: int
    b1: dict | None
    serving: dict
    repo: dict
    t0: dict
    notes: str


@dataclass(frozen=True)
class CallPlan:
    """메모리 전용: body는 전송 bytes이며 JsonRecord 왕복 대상이 아니다 (§8-6 C)."""

    call_id: str
    logical_id: str
    kind: str
    question_ids: list[str]
    question_types: dict[str, str]
    body: bytes
    request_sha256: str
    request: Request | None
    b1_call: B1Call | None
    rendered: Rendered
    local_errors: list[str]


@dataclass(frozen=True)
class RetryPolicy(JsonRecord):
    """configs/policy.yaml 의 retry — 검사는 contract/policy, 읽기는 io/policy."""

    max_attempts: int
    http_statuses: list[int]
    backoff_seconds: list[float]


@dataclass(frozen=True)
class Decision(JsonRecord):
    terminal: bool
    wait_s: float | None


@dataclass(frozen=True)
class RunSummary(JsonRecord):
    n_logical: int
    n_skipped_final: int
    n_calls: int
    n_sent: int
    n_recovered: int
    by_status: dict[str, int]
    n_deferred: int = 0
