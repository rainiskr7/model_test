"""무엇: 요청·호출·시도·최종 기록 · 입력: JSON 필드 · 출력: dataclass · 계약 §2·§5."""

from dataclasses import dataclass
from typing import Any

from .base import JsonRecord
from .results import LengthInfo, ParsedAnswer


@dataclass(frozen=True)
class Request(JsonRecord):
    model: str
    state: str
    questions: dict[str, dict[str, Any]]


@dataclass(frozen=True)
class AttemptRecord(JsonRecord):
    call_id: str
    logical_id: str
    attempt: int
    session_id: str
    started_at: str
    ended_at: str
    latency_ms: float
    http_status: int | None
    retry_after: str | float | None
    transport_error: str | None
    terminal: bool
    request_sha256: str
    response_raw: str | dict[str, str]


@dataclass(frozen=True)
class CallRecord(JsonRecord):
    call_id: str
    attempts: int
    status: str
    reason: str | None
    warnings: list[str]
    request_sha256: str
    length: LengthInfo | None
    usage: dict[str, Any] | None
    answers_parsed: dict[str, ParsedAnswer] | None
    label_map: dict[str, str] | None = None
    top_logprobs_raw: Any = None


@dataclass(frozen=True)
class FinalRecord(JsonRecord):
    logical_id: str
    status: str
    reason: str | None
    answered_over_limit: bool
    warnings: list[str]
    calls: list[CallRecord]
    derived_from: str | None = None
