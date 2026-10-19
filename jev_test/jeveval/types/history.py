"""무엇: 역사 읽기 경계 · 입력: 저장 산출물 · 출력: 불변 읽기/검사 값 · 계약 §5-1b."""

from dataclasses import dataclass
from pathlib import Path

from .records import FinalRecord
from .specs import TaskSpec


@dataclass(frozen=True)
class HistoryStage:
    name: str
    present: bool
    finals: list[FinalRecord]
    expected: list[str] | None
    warnings: list[str]


@dataclass(frozen=True)
class History:
    directory: Path
    artifacts: dict
    hashes: dict[str, str]
    stages: list[HistoryStage]
    errors: list[str]
    task: TaskSpec | None = None


@dataclass(frozen=True)
class StageCheck:
    name: str
    status: str
    expected: int | None
    finalized: int
    pending: int | None
    by_status: dict[str, int]


@dataclass(frozen=True)
class HistoryCheck:
    status: str
    reasons: list[str]
    stages: list[StageCheck]
