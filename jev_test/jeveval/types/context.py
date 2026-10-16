"""무엇: 명령 공유 문맥 · 입력: 검증된 설정·분할·fingerprint·단계 기록 · 출력: 메모리 전용 dataclass · 계약 §8-1·§8-6 E."""

from dataclasses import dataclass
from pathlib import Path

from .contract import B1Config
from .outcomes import RequestOutcome
from .records import FinalRecord
from .run import ModelConfig, RetryPolicy
from .specs import Item, SplitPlan, TaskSpec


@dataclass(frozen=True)
class RunContext:
    """configuration 이 만들고, restore·run 이 directory·fingerprint 를 채운 사본(replace)으로 이어 쓴다."""

    root: Path
    model_path: Path
    task_path: Path
    cfg: ModelConfig
    task: TaskSpec
    plan: SplitPlan
    b1: B1Config
    policy: RetryPolicy
    directory: Path | None = None
    fingerprint: dict | None = None


@dataclass(frozen=True)
class StageData:
    """한 단계의 final 기록·logical_id → Item·RequestOutcome·읽기 경고."""

    finals: list[FinalRecord]
    items: dict[str, Item]
    outcomes: list[RequestOutcome]
    warnings: list[str]
