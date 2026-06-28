"""벤치마크 결과 표준 schema (Pydantic v2).

각 bench (k_mmbench, koffvqa, kreta, b3, b4 등) 가 따르는 공통 베이스 schema +
sanity check 가 validation 으로 활용. 새 bench 추가 시 BenchmarkResult 상속.

운영 정책:
- 기존 bench 들의 결과 JSON 은 현행 유지 (broken backward compat 안 됨)
- 새 bench 부터 schema 채택 권장
- sanity check 가 schema-aware 검증 우선, legacy 결과는 fallback 으로 키 기반 검사

Why: 평가 결과의 "성공 exit + 의미 없는 0건" 함정 (B-3 이미지 누락 사례) 을
sanity check 가 즉시 잡도록 표준화. 새 bench 추가 시 LLM 이 schema 따르면
자동으로 sanity check 에 포함됨.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


class BenchmarkResult(BaseModel):
    """모든 bench 결과의 공통 베이스.

    필수: benchmark, model, total
    sanity check 가 total==0 면 강한 경고.
    """

    benchmark: str = Field(..., description="벤치마크 명 (e.g. 'K-MMBench')")
    model: str = Field(..., description="평가된 모델 ID")
    total: int = Field(..., ge=0, description="평가 샘플 총 수")

    @model_validator(mode="after")
    def _warn_zero_total(self) -> "BenchmarkResult":
        # Pydantic 은 raise 안 함 (single source of fail-fast 는 호출자 책임)
        # 단 total==0 은 의도된 케이스도 있을 수 있어 schema validation 으로 차단 안 함
        return self


class AccuracyBenchmark(BenchmarkResult):
    """정답률 기반 bench (k_mmbench, kreta 등)."""

    correct: int = Field(..., ge=0)
    accuracy: float = Field(..., ge=0.0, le=1.0)
    by_category: Optional[dict[str, Any]] = None


class StructuredOutputBenchmark(BenchmarkResult):
    """JSON 출력 검증 bench (b3_structured_output)."""

    json_parse_rate: float = Field(..., ge=0.0, le=1.0)
    schema_pass_rate: float = Field(..., ge=0.0, le=1.0)
    value_match_rate: Optional[float] = Field(None, ge=0.0, le=1.0)
    by_category: Optional[dict[str, Any]] = None


class LatencyBenchmark(BaseModel):
    """latency profile bench (b4_latency_profile). total 대신 conditions 사용."""

    benchmark: str
    model: str
    conditions: list[dict[str, Any]] = Field(..., min_length=1)


def detect_and_validate(d: dict, file_path: str = "<json>") -> tuple[str, Optional[str]]:
    """bench 결과 JSON 의 schema 자동 감지 + validation.

    Returns: (kind, error_msg)
      - kind: 'accuracy' | 'structured' | 'latency' | 'unknown'
      - error_msg: None 이면 OK, 문자열이면 warning/error 메시지

    sanity check (run_all.sh) 가 이 함수 호출해서 0건 결과 / schema 위반 탐지.
    """
    if "conditions" in d:
        try:
            LatencyBenchmark.model_validate(d)
            return "latency", None
        except Exception as e:
            return "latency", f"{file_path}: latency schema 위반 — {e}"
    if "json_parse_rate" in d and "schema_pass_rate" in d:
        try:
            r = StructuredOutputBenchmark.model_validate(d)
            if r.total == 0:
                return "structured", f"{file_path}: structured output total=0 (이미지 누락 등)"
            return "structured", None
        except Exception as e:
            return "structured", f"{file_path}: structured schema 위반 — {e}"
    if "accuracy" in d and "correct" in d:
        try:
            r = AccuracyBenchmark.model_validate(d)
            if r.total == 0:
                return "accuracy", f"{file_path}: accuracy total=0"
            if r.accuracy < 0.05:
                return "accuracy", f"{file_path}: accuracy={r.accuracy:.3f} 매우 낮음 (broken template 의심)"
            return "accuracy", None
        except Exception as e:
            return "accuracy", f"{file_path}: accuracy schema 위반 — {e}"
    return "unknown", None  # legacy / KRETA 같은 모델별 키 구조는 별도 처리
