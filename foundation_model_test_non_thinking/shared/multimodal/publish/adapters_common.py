"""Shared counts, source configuration and publication-result assembly."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping

from shared.multimodal.publish.classify import classify_record
from shared.multimodal.publish.schema import COMPARISON_CRITICAL_UNKNOWN, PublishStatus, RecordClass


EXPECTED_COUNTS = {
    "k_dtcbench": 240,
    "k_mmbench": 4329,
    "mtvqa_kr": 558,
    "kreta": 2577,
    "koffvqa": 275,
    "koffvqa_api_judge": 275,
}

BENCHMARK_IDS = {
    "k_dtcbench": "K-DTCBench",
    "k_mmbench": "K-MMBench",
    "mtvqa_kr": "MTVQA-KR",
    "kreta": "KRETA",
    "koffvqa": "KOFFVQA",
    "koffvqa_api_judge": "KOFFVQA-judge",
    "b3_structured_output": "B3-structured-output",
    "b4_latency_profile": "B4-latency-profile",
}

BENCHMARK_KEYS = {
    value.lower(): key for key, value in BENCHMARK_IDS.items()
}
BENCHMARK_KEYS.update({key.lower(): key for key in BENCHMARK_IDS})


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _fraction(num: int, den: int, unit: str = "fraction") -> dict[str, Any]:
    return {"numerator": num, "denominator": den, "value": num / den if den else None, "unit": unit}


def _counts(records: Iterable[Mapping[str, Any]], response_field: str = "response") -> tuple[dict[str, int], list[tuple[Mapping[str, Any], RecordClass]]]:
    classified = [(record, classify_record(record, response_field)) for record in records]
    counts = {
        "attempted": len(classified),
        "measured": sum(kind is RecordClass.MEASURED for _, kind in classified),
        "errored": sum(kind is RecordClass.ERRORED for _, kind in classified),
        "unresolved": sum(kind is RecordClass.UNRESOLVED for _, kind in classified),
    }
    return counts, classified


def _run_config(summary: Mapping[str, Any], source_dir: Path) -> dict[str, Any]:
    config = summary.get("run_config")
    if isinstance(config, dict):
        return config
    path = source_dir / "run_config.json"
    if path.exists():
        value = load_json(path)
        if isinstance(value, dict):
            return value
    return {}


def _base_result(
    *,
    benchmark_key: str,
    variant: str,
    model: str,
    source_dir: Path,
    source_files: list[Path],
    counts: Mapping[str, int],
    metrics: Mapping[str, Any],
    protocol: Mapping[str, Any],
    completed_at_utc: str | None,
    failures: list[str],
    warnings: list[str],
    forced_status: PublishStatus | None = None,
    provisional: bool = False,
) -> dict[str, Any]:
    critical = sorted(set(protocol.get("unknown") or []) & COMPARISON_CRITICAL_UNKNOWN)
    if failures:
        status = PublishStatus.REJECTED
    elif forced_status is not None:
        status = forced_status
    elif critical:
        status = PublishStatus.INSUFFICIENT_PROVENANCE
        failures = ["비교에 필요한 provenance가 복원되지 않음: " + ", ".join(critical)]
    else:
        status = PublishStatus.LEGACY_REVALIDATED
    noncritical = sorted(set(protocol.get("unknown") or []) - COMPARISON_CRITICAL_UNKNOWN)
    if noncritical and status.publishable:
        warnings.append("비교 비핵심 provenance 미기록: " + ", ".join(noncritical))
    return {
        "benchmark_id": BENCHMARK_IDS[benchmark_key],
        "benchmark_key": benchmark_key,
        "variant": variant,
        "model": model,
        "source_dir": source_dir,
        "source_files": source_files,
        "status": status,
        "publishable": status.publishable,
        "provisional": provisional,
        "aggregation_allowed": False,
        "completed_at_utc": completed_at_utc,
        "counts": dict(counts),
        "metrics": dict(metrics),
        "protocol": dict(protocol),
        "failures": failures,
        "warnings": warnings,
    }


def _same_metric(stored: Any, calculated: Any) -> bool:
    if stored is None or calculated is None:
        return stored is None and calculated is None
    if isinstance(stored, bool) or isinstance(calculated, bool):
        return stored is calculated
    if isinstance(stored, (int, float)) and isinstance(calculated, (int, float)):
        return math.isclose(float(stored), float(calculated), rel_tol=1e-12, abs_tol=1e-12)
    return stored == calculated
