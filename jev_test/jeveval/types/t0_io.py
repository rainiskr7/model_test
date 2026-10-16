"""무엇: T0 단계 경계 자료형 · 입력: 확정 입력/참조 핸들 · 출력: 단계 전달 객체 · 계약 §8-7."""

from dataclasses import dataclass
from typing import Any

from .base import JsonRecord
from .t0 import T0Boundary


@dataclass(frozen=True)
class T0Input(JsonRecord):
    case_id: str
    body: dict
    reference_body: dict
    request_sha256: str
    envelope_sha256: str
    reference_envelope_sha256: str
    lengths: list[int] | None
    boundary: T0Boundary | None


@dataclass(frozen=True)
class T0Inputs:
    metadata: dict
    rows: list[T0Input]
    sha256: str


@dataclass(frozen=True)
class T0Reference:
    family: str
    model: Any
    module: Any
    processor: Any = None
    answer_module: Any = None
    server: Any = None
    max_length: int | None = None


@dataclass(frozen=True)
class T0Policy(JsonRecord):
    """configs/t0/tolerance_v1.yaml — 검사는 contract/t0_policy, 읽기는 io/t0_policy. sha256 은 파일 바이트 해시(단계 연결용)."""

    repeats: int
    max_variation: float
    variants: dict[str, list[str]]
    sha256: str


@dataclass(frozen=True)
class T0Sources:
    rows: dict
    groups: dict
    pools: dict
    seed: int
