"""KOFFVQA generation and judge publication adapters."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Mapping

from shared.multimodal.publish.adapters_common import (
    EXPECTED_COUNTS, load_json, _counts, _run_config, _base_result,
)
from shared.multimodal.publish.adapters_protocol import (
    _add_decoding, _dataset_revision, _judge_protocol,
)
from shared.multimodal.publish.schema import (
    PublishStatus, dataset_item_digest, make_protocol, sha256_file,
)


def _session_of(path: Path) -> str | None:
    """The results session a path belongs to: results/<model>/<session>/..."""

    parts = Path(path).parts
    if "results" in parts:
        index = parts.index("results")
        if len(parts) > index + 2:
            return parts[index + 2]
    return None


def _prediction_session(summary: Mapping[str, Any], sibling: Path) -> str | None:
    predfile = summary.get("predfile")
    return _session_of(Path(predfile)) if predfile else _session_of(sibling)


def _aggregate_judge_rows(rows: list, summary: Mapping[str, Any], failures: list[str]) -> tuple:
    """Judge 유효 점수를 재집계하고 저장 요약과 대조한다."""
    counts = {
        "attempted": len(rows),
        "measured": 0,
        "errored": 0,
        "unresolved": 0,
    }
    scores: list[int] = []
    item_keys: list[str] = []
    for row in rows:
        item_key = row.get("dataset_item_id")
        if item_key is None:
            failures.append("judge row dataset_item_id가 누락됨")
        else:
            item_keys.append(str(item_key))
        if row.get("error"):
            counts["errored"] += 1
            continue
        score = row.get("score")
        if isinstance(score, bool) or not isinstance(score, int) or not 0 <= score <= 10:
            counts["unresolved"] += 1
            continue
        counts["measured"] += 1
        scores.append(score)
    # Non-accuracy benchmarks use correct_measured for records that produced
    # a contract-valid primary measurement (a valid judge score here).
    counts["correct_measured"] = counts["measured"]
    if counts["attempted"] != EXPECTED_COUNTS["koffvqa_api_judge"]:
        failures.append(f"기대 건수 {EXPECTED_COUNTS['koffvqa_api_judge']}와 다름")
    if counts["errored"]:
        failures.append("judge 오류가 포함됨")
    if counts["unresolved"]:
        failures.append("0~10 정수 아닌 judge 점수가 포함됨")
    if len(item_keys) != len(rows) or len(set(item_keys)) != len(item_keys):
        failures.append("judge dataset item key가 누락되었거나 중복됨")
    item_digest = dataset_item_digest(item_keys) if len(item_keys) == len(rows) else None
    if summary.get("scored") != len(scores):
        failures.append("raw 재집계와 summary scored가 일치하지 않음")
    average = sum(scores) / len(scores) if scores else None
    stored_average = summary.get("avg_score")
    if average is not None and (not isinstance(stored_average, (int, float)) or not math.isclose(average, stored_average, abs_tol=1e-12)):
        failures.append("raw 재집계와 summary 평균이 일치하지 않음")
    return counts, scores, item_digest, average


def adapt_koffvqa(source_dir: Path) -> dict[str, Any]:
    raw_path, summary_path = source_dir / "results.json", source_dir / "summary.json"
    failures: list[str] = []
    warnings: list[str] = []
    try:
        records, summary = load_json(raw_path), load_json(summary_path)
    except Exception as exc:
        records, summary = [], {}
        failures.append(f"산출물 읽기 실패: {type(exc).__name__}")
    if not isinstance(records, list) or not isinstance(summary, dict):
        records, summary = [], {}
        failures.append("results.json/summary.json 형식이 올바르지 않음")
    counts, _ = _counts(records, "prediction")
    if counts["attempted"] != EXPECTED_COUNTS["koffvqa"]:
        failures.append(f"기대 건수 {EXPECTED_COUNTS['koffvqa']}와 다름")
    if counts["errored"]:
        failures.append("오류 응답이 포함됨")
    if counts["unresolved"]:
        failures.append("미해결 응답이 포함됨")
    config = _run_config(summary, source_dir)
    recorded: dict[str, Any] = {"benchmark": "KOFFVQA", "limit": (config.get("extra") or {}).get("limit")}
    inferred: dict[str, Any] = {}
    unknown: list[str] = []
    revision = _dataset_revision(config)
    if revision:
        recorded["dataset_revision"] = revision
    else:
        unknown.append("dataset_revision")
    _add_decoding(config, recorded, unknown)
    protocol = make_protocol(recorded, inferred, unknown)
    model = str(summary.get("model") or (config.get("model") or {}).get("name") or source_dir.parents[3].name)
    return _base_result(
        benchmark_key="koffvqa",
        variant="generation",
        model=model,
        source_dir=source_dir,
        source_files=[raw_path, summary_path] + sorted(source_dir.glob("*_gen.xlsx")),
        counts=counts,
        metrics={"axes": []},
        protocol=protocol,
        completed_at_utc=config.get("timestamp_utc"),
        failures=failures,
        warnings=warnings,
        forced_status=PublishStatus.UNSCORED,
    )


def adapt_koffvqa_judge(source_dir: Path) -> dict[str, Any]:
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
    counts, scores, item_digest, average = _aggregate_judge_rows(rows, summary, failures)

    sibling = source_dir.parent / "koffvqa"
    candidates = sorted(sibling.glob("*_gen.xlsx"))
    recorded_sha = summary.get("prediction_sha256")
    if not recorded_sha:
        failures.append("prediction SHA 기록이 없음")
    elif not candidates or all(sha256_file(path) != recorded_sha for path in candidates):
        failures.append("prediction SHA가 생성 산출물과 일치하지 않음")
    config = _run_config(summary, source_dir)
    try:
        generation_summary = load_json(sibling / "summary.json")
        generation_revision = _dataset_revision(_run_config(generation_summary, sibling))
    except Exception:
        generation_revision = None
    # A judged run answers one of two different questions.  Regenerating the
    # target responses and judging them measures the whole pipeline; re-judging
    # bytes that already exist measures only the judge.  Both used to land in one
    # cohort under one tolerance, so a spread could not be attributed.  The
    # session that produced the predictions decides which this is.
    prediction_session = _prediction_session(summary, sibling)
    judge_session = _session_of(source_dir)
    rejudge = bool(prediction_session and judge_session and prediction_session != judge_session)
    protocol = _judge_protocol(summary, config, recorded_sha, item_digest, rejudge, generation_revision)
    metrics = {
        "axes": [{"name": "rubric", "value": average, "unit": "score/10", "numerator": sum(scores), "denominator": len(scores)}]
    }
    model = str(summary.get("target_model") or (config.get("model") or {}).get("name") or source_dir.parents[3].name)
    return _base_result(
        benchmark_key="koffvqa_api_judge",
        variant="api_judge_rejudge" if rejudge else "api_judge_end_to_end",
        model=model,
        source_dir=source_dir,
        source_files=[raw_path, summary_path] + candidates,
        counts=counts,
        metrics=metrics,
        protocol=protocol,
        completed_at_utc=config.get("timestamp_utc"),
        failures=failures,
        warnings=warnings,
        provisional=True,
    )
