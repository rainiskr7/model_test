"""Structured-output and latency publication adapters for customB."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping

from shared.multimodal.publish.adapters_common import (
    load_json, _fraction, _counts, _run_config, _base_result, _same_metric,
)
from shared.multimodal.publish.adapters_protocol import _add_decoding
from shared.multimodal.publish.schema import make_protocol


def _b3_raw_metrics(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    parse_ok = sum(row.get("parse_ok") is True for row in rows)
    schema_ok = sum(
        isinstance(check := row.get("schema_check"), Mapping)
        and check.get("required_fields_present") is True
        and check.get("type_match") is True
        for row in rows
    )
    value_rates = [
        check.get("match_rate")
        for row in rows
        if isinstance(check := row.get("value_check"), Mapping)
        and isinstance(check.get("match_rate"), (int, float))
        and not isinstance(check.get("match_rate"), bool)
    ]
    return {
        "json_parse_rate": parse_ok / total if total else 0.0,
        "schema_pass_rate": schema_ok / total if total else 0.0,
        "value_match_rate": sum(value_rates) / len(value_rates) if value_rates else None,
        "json_parse_numerator": parse_ok,
        "schema_pass_numerator": schema_ok,
        "value_count": len(value_rates),
    }


def adapt_b3(source_dir: Path) -> dict[str, Any]:
    raw_path, summary_path = source_dir / "results.json", source_dir / "summary.json"
    failures: list[str] = []
    warnings: list[str] = []
    try:
        rows, summary = load_json(raw_path), load_json(summary_path)
    except Exception as exc:
        rows, summary = [], {}
        failures.append(f"산출물 읽기 실패: {type(exc).__name__}")
    if not isinstance(rows, list) or not isinstance(summary, dict):
        rows, summary = [], {}
        failures.append("results.json/summary.json 형식이 올바르지 않음")
    counts, _ = _counts(rows)
    config = _run_config(summary, source_dir)
    manifest_size = (config.get("extra") or {}).get("manifest_size")
    if counts["attempted"] <= 0:
        failures.append("total=0")
    if not isinstance(manifest_size, int) or manifest_size <= 0 or counts["attempted"] != manifest_size:
        failures.append("manifest 전 항목을 시도하지 않음")
    if counts["errored"] or counts["unresolved"]:
        failures.append("오류 또는 미해결 응답이 포함됨")
    raw_metrics = _b3_raw_metrics(rows)
    counts["correct_measured"] = raw_metrics["schema_pass_numerator"]
    for key in ("json_parse_rate", "schema_pass_rate", "value_match_rate"):
        if not _same_metric(summary.get(key), raw_metrics[key]):
            failures.append(f"raw 재집계와 summary {key}가 일치하지 않음")
    recorded = {"benchmark": "B3", "manifest_size": manifest_size, "limit": (config.get("extra") or {}).get("limit")}
    unknown: list[str] = []
    _add_decoding(config, recorded, unknown)
    protocol = make_protocol(recorded, {}, unknown)
    total = counts["attempted"]
    axes = [
        {"name": "json_parse", **_fraction(raw_metrics["json_parse_numerator"], total)},
        {"name": "schema_pass", **_fraction(raw_metrics["schema_pass_numerator"], total)},
    ]
    if raw_metrics["value_match_rate"] is not None:
        axes.append({
            "name": "value_match", "value": raw_metrics["value_match_rate"],
            "unit": "fraction", "numerator": None,
            "denominator": raw_metrics["value_count"],
        })
    model = str(summary.get("model") or (config.get("model") or {}).get("name") or source_dir.parents[3].name)
    return _base_result(
        benchmark_key="b3_structured_output", variant="manifest", model=model,
        source_dir=source_dir, source_files=[raw_path, summary_path], counts=counts,
        metrics={"axes": axes}, protocol=protocol, completed_at_utc=config.get("timestamp_utc"),
        failures=failures, warnings=warnings,
    )


def _percentiles(values: Iterable[Any]) -> dict[str, Any]:
    numeric = [
        float(value) for value in values
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    ]
    if not numeric:
        return {"p50": None, "p95": None, "p99": None, "mean": None, "n": 0}
    ordered = sorted(numeric)
    n = len(ordered)

    def percentile(p: float) -> float:
        if n == 1:
            return ordered[0]
        position = p / 100.0 * (n - 1)
        low = int(position)
        high = min(low + 1, n - 1)
        fraction = position - low
        return ordered[low] * (1 - fraction) + ordered[high] * fraction

    return {
        "p50": percentile(50), "p95": percentile(95), "p99": percentile(99),
        "mean": sum(ordered) / n, "n": n,
    }


def _b4_raw_summary(name: str, entries: list[Mapping[str, Any]]) -> dict[str, Any]:
    def completion_tokens(row: Mapping[str, Any]) -> Any:
        return row.get("completion_tokens") or row.get("chunks")

    def tokens_per_second(row: Mapping[str, Any]) -> float | None:
        tokens, total = completion_tokens(row), row.get("total")
        if not isinstance(tokens, (int, float)) or not tokens or not isinstance(total, (int, float)) or not total:
            return None
        return float(tokens) / float(total)

    return {
        "condition": name,
        "reps": len(entries),
        "successful": sum(row.get("ttft") is not None for row in entries),
        "failed": sum(bool(row.get("error")) for row in entries),
        "ttft": _percentiles(row.get("ttft") for row in entries),
        "total": _percentiles(row.get("total") for row in entries),
        "completion_tokens": _percentiles(completion_tokens(row) for row in entries),
        "tokens_per_sec": _percentiles(tokens_per_second(row) for row in entries),
    }


def _b4_summary_matches(stored: Mapping[str, Any], calculated: Mapping[str, Any]) -> bool:
    for key in ("condition", "reps", "successful", "failed"):
        if stored.get(key) != calculated.get(key):
            return False
    for metric in ("ttft", "total", "completion_tokens", "tokens_per_sec"):
        stored_metric = stored.get(metric)
        calculated_metric = calculated[metric]
        if not isinstance(stored_metric, Mapping):
            return False
        if any(not _same_metric(stored_metric.get(key), calculated_metric[key]) for key in ("p50", "p95", "p99", "mean", "n")):
            return False
    return True


def _aggregate_latency_conditions(runs, summary, expected_names, reps, *, failures) -> tuple:
    """Reaggregate latency records and append ordered consistency failures."""
    attempted = measured = errored = unresolved = 0
    for name in expected_names:
        entries = runs.get(name)
        if not isinstance(entries, list) or not isinstance(reps, int) or len(entries) != reps:
            failures.append("condition/rep 완주 조건을 충족하지 않음")
            continue
        attempted += len(entries)
        for entry in entries:
            if entry.get("error"):
                errored += 1
            elif entry.get("ttft") is None or entry.get("total") is None:
                unresolved += 1
            else:
                measured += 1
    if set(runs) != expected_names:
        failures.append("condition 집합이 run_config와 일치하지 않음")
    if errored or unresolved:
        failures.append("latency 호출 실패 또는 미해결 값이 포함됨")
    by_name = {entry.get("condition"): entry for entry in (summary.get("conditions") or []) if isinstance(entry, dict)}
    raw_by_name: dict[str, dict[str, Any]] = {}
    for name in expected_names:
        entries = runs.get(name)
        if isinstance(entries, list):
            raw_by_name[name] = _b4_raw_summary(name, entries)
    if set(by_name) != expected_names:
        failures.append("summary condition 집합이 일치하지 않음")
    else:
        for name in expected_names:
            entry = by_name[name]
            calculated = raw_by_name.get(name)
            if calculated is None or not _b4_summary_matches(entry, calculated):
                failures.append("runs.json 재집계와 summary condition 수치가 일치하지 않음")
                break
    counts = {
        "attempted": attempted,
        "measured": measured,
        "errored": errored,
        "unresolved": unresolved,
        # For latency, a completed record is the contract-valid measurement.
        "correct_measured": measured,
    }
    return counts, raw_by_name


def adapt_b4(source_dir: Path) -> dict[str, Any]:
    runs_path, summary_path = source_dir / "runs.json", source_dir / "summary.json"
    failures: list[str] = []
    warnings: list[str] = []
    try:
        runs, summary = load_json(runs_path), load_json(summary_path)
    except Exception as exc:
        runs, summary = {}, {}
        failures.append(f"산출물 읽기 실패: {type(exc).__name__}")
    if not isinstance(runs, dict) or not isinstance(summary, dict):
        runs, summary = {}, {}
        failures.append("runs.json/summary.json 형식이 올바르지 않음")
    config = _run_config(summary, source_dir)
    extra = config.get("extra") or {}
    expected_names = {"text_only", "image_256px", "image_1024px"}
    if not extra.get("skip_multi_image"):
        expected_names.add("multi_image_3x512px")
    reps = extra.get("reps_per_condition")
    counts, raw_by_name = _aggregate_latency_conditions(
        runs, summary, expected_names, reps, failures=failures
    )
    axes: list[dict[str, Any]] = []
    for name in sorted(expected_names):
        entry = raw_by_name.get(name) or {}
        for metric, unit in (("ttft", "seconds"), ("total", "seconds"), ("tokens_per_sec", "tokens/second")):
            values = entry.get(metric) or {}
            for percentile in ("p50", "p95", "p99"):
                value = values.get(percentile)
                if isinstance(value, (int, float)):
                    axes.append({"name": f"{name}:{metric}:{percentile}", "value": value, "unit": unit})
    recorded = {
        "benchmark": "B4",
        "conditions": sorted(expected_names),
        "reps_per_condition": reps,
        "prompt": extra.get("prompt"),
    }
    unknown: list[str] = []
    _add_decoding(config, recorded, unknown)
    protocol = make_protocol(recorded, {}, unknown)
    model = str(summary.get("model") or (config.get("model") or {}).get("name") or source_dir.parents[3].name)
    return _base_result(
        benchmark_key="b4_latency_profile", variant="latency", model=model,
        source_dir=source_dir, source_files=[runs_path, summary_path], counts=counts,
        metrics={"axes": axes}, protocol=protocol, completed_at_utc=config.get("timestamp_utc"),
        failures=failures, warnings=warnings,
    )
