"""Accuracy aggregation and KRETA parsing over raw multimodal responses."""

from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

from shared.multimodal.publish.classify import classify_record
from shared.multimodal.publish.adapters_common import (
    BENCHMARK_IDS, BENCHMARK_KEYS, EXPECTED_COUNTS,
    load_json, _fraction, _counts, _run_config, _base_result,
)
from shared.multimodal.publish.adapters_protocol import (
    _add_dataset_provenance, _add_decoding, _kreta_protocol,
)
from shared.multimodal.publish.schema import (
    KRETA_ANSWER_PARSER_SPEC, RecordClass, dataset_item_digest, make_protocol,
)


def _score_classified_records(key, classified, response_field, verify_stored_prediction) -> tuple:
    """Score classified responses and retain parser disagreement diagnostics."""
    correct = 0
    by_category: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    score_accuracy = key != "koffvqa"
    stored_prediction_mismatches = 0
    disagreement_ours_empty = 0
    disagreement_different_choice = 0
    no_answer = 0
    for row, kind in classified:
        category = str(row.get("category", "overall"))
        by_category[category][1] += 1
        if kind is not RecordClass.MEASURED or not score_accuracy:
            continue
        response = row[response_field]
        if key == "mtvqa_kr":
            is_correct = any(_mtvqa_match(response, str(gold)) for gold in (row.get("gold") or []))
        elif key == "kreta":
            parsed = parse_kreta_response(response)
            stored = str(row.get("pred_indexs", "")).strip().upper()
            if verify_stored_prediction and parsed != stored:
                stored_prediction_mismatches += 1
                if not parsed and stored in {"A", "B", "C", "D"}:
                    disagreement_ours_empty += 1
                elif parsed in {"A", "B", "C", "D"} and stored in {"A", "B", "C", "D"}:
                    disagreement_different_choice += 1
            if not parsed:
                no_answer += 1
            is_correct = parsed == str(row.get("answer", "")).strip().upper()
        else:
            is_correct = _choice(response) == str(row.get("answer", "")).strip().upper()
        if is_correct:
            correct += 1
            by_category[category][0] += 1
    return correct, by_category, stored_prediction_mismatches, disagreement_ours_empty, disagreement_different_choice, no_answer


def summarize_records(
    benchmark_id: str,
    records: Iterable[Mapping[str, Any]],
    *,
    response_field: str = "response",
    expected_count: int | None = None,
    verify_stored_prediction: bool = True,
) -> dict[str, Any]:
    """Pure runner/adapter aggregation over raw records.

    Stored ``correct`` fields are intentionally ignored.  Only records
    classified as MEASURED are eligible for the numerator.
    """

    rows = list(records)
    key = BENCHMARK_KEYS.get(benchmark_id.lower())
    if key not in {"k_dtcbench", "k_mmbench", "mtvqa_kr", "kreta", "koffvqa"}:
        raise ValueError(f"summarize_records does not support {benchmark_id!r}")
    counts, classified = _counts(rows, response_field)
    (correct, by_category, stored_prediction_mismatches, disagreement_ours_empty,
     disagreement_different_choice, no_answer) = _score_classified_records(
        key, classified, response_field, verify_stored_prediction
    )
    counts["correct_measured"] = correct
    failures: list[str] = []
    if expected_count is not None and counts["attempted"] != expected_count:
        failures.append(f"기대 건수 {expected_count}와 다름")
    if counts["errored"]:
        failures.append(f"오류 응답 {counts['errored']}건 포함")
    if counts["unresolved"]:
        failures.append(f"미해결 응답 {counts['unresolved']}건 포함")
    warnings: list[str] = []
    if stored_prediction_mismatches:
        warnings.append(
            f"상류 parser와 {stored_prediction_mismatches}행 불일치 "
            f"(우리 무답 {disagreement_ours_empty}, 다른 선택지 {disagreement_different_choice}) "
            "— 독립 재채점 점수임"
        )
    no_answer_rate = no_answer / counts["attempted"] if counts["attempted"] else 0.0
    if key == "kreta" and no_answer_rate > 0.10:
        warnings.append(
            f"무답 {no_answer}건 ({100 * no_answer_rate:.1f}%) — 응답이 지시된 형식을 "
            "벗어나 절단됨. 점수를 능력 차이로만 해석하지 말 것"
        )
    return {
        "counts": counts,
        "correct": correct,
        "accuracy": correct / counts["attempted"] if counts["attempted"] else 0.0,
        "by_category": {
            category: {
                "correct": values[0],
                "total": values[1],
                "accuracy": values[0] / values[1] if values[1] else 0.0,
            }
            for category, values in sorted(by_category.items())
        },
        "accuracy_strict": _fraction(correct, counts["attempted"]),
        "accuracy_conditional": _fraction(correct, counts["measured"]),
        "publish_status": {"publishable": not failures, "failures": failures},
        "warnings": warnings,
        "stored_prediction_mismatches": stored_prediction_mismatches,
        "disagreement_ours_empty": disagreement_ours_empty,
        "disagreement_different_choice": disagreement_different_choice,
        "no_answer": no_answer,
    }


def parse_kreta_response(response: Any) -> str:
    """Parse only the answer forms promised by KRETA prompts.

    The parser deliberately does not scan arbitrary prose for the first A-D;
    doing so recreates the upstream accidental-match failure mode.
    """

    if not isinstance(response, str):
        return ""
    text = re.sub(r"[*_`]", "", response.strip().upper())
    explicit: list[tuple[int, str]] = []
    for pattern in KRETA_ANSWER_PARSER_SPEC["explicit_patterns"]:
        explicit.extend((match.start(), match.group(1)) for match in re.finditer(pattern, text))
    if explicit:
        return max(explicit)[1]
    compact = re.sub(r"[\s#>]+", "", text)
    if len(compact) <= KRETA_ANSWER_PARSER_SPEC["short_max_compact_chars"]:
        short = re.fullmatch(KRETA_ANSWER_PARSER_SPEC["short_pattern"], compact)
        if short:
            return short.group(1)
    lines = [
        re.sub(r"^[\s>#]+|[\s#]+$", "", line).strip()
        for line in text.splitlines()
        if line.strip()
    ]
    if lines:
        last = re.fullmatch(KRETA_ANSWER_PARSER_SPEC["last_line_pattern"], lines[-1])
        if last:
            return last.group(1)
    return ""


def _choice(response: str) -> str:
    if not response:
        return ""
    text = response.strip().upper()
    if text and text[0] in "ABCD":
        return text[0]
    for pattern in (
        r"정답[은:]?\s*[\(\[]?\s*([ABCD])",
        r"답[은:]?\s*[\(\[]?\s*([ABCD])",
        r"[\(\[]([ABCD])[\)\]]",
        r"\b([ABCD])\s*번",
        r"\b([ABCD])\s*[\)\]\.]",
        r"\b([ABCD])\b",
    ):
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return ""


def _normalize_answer(value: str) -> str:
    if not value:
        return ""
    value = unicodedata.normalize("NFKC", value).strip()
    value = re.sub(r"^[\'\"`「『\(\[<]+|[\'\"`」』\)\]>.,!?:;]+$", "", value).strip()
    return value.lower()


def _mtvqa_match(prediction: str, gold: str) -> bool:
    pred, expected = _normalize_answer(prediction), _normalize_answer(gold)
    if not pred or not expected:
        return False
    if pred == expected:
        return True
    if expected in re.findall(r"\S+", pred):
        return True
    if len(expected) > 3 and expected in pred:
        return True
    return len(pred) >= 2 and pred in expected


def _accuracy_item_keys(
    benchmark_key: str,
    records: list[Mapping[str, Any]],
) -> tuple[list[str], str | None]:
    if benchmark_key == "mtvqa_kr":
        if any(row.get("row_idx") is None or row.get("qa_idx") is None for row in records):
            return [], "(row_idx, qa_idx)가 누락됨"
        keys = [f"{row['row_idx']}\t{row['qa_idx']}" for row in records]
    else:
        if any(row.get("index") is None for row in records):
            return [], "index가 누락됨"
        keys = [str(row["index"]) for row in records]
    if len(set(keys)) != len(keys):
        return keys, "dataset item key가 중복됨"
    return keys, None


def _accuracy_protocol(
    benchmark_key: str,
    summary: Mapping[str, Any],
    source_dir: Path,
    item_digest: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    config = _run_config(summary, source_dir)
    recorded: dict[str, Any] = {"benchmark": BENCHMARK_IDS[benchmark_key]}
    inferred: dict[str, Any] = {}
    unknown: list[str] = []
    _add_dataset_provenance(config, recorded)
    if item_digest:
        recorded["dataset_item_digest"] = item_digest
    else:
        unknown.append("dataset_item_digest")
    extra = config.get("extra") or {}
    if benchmark_key == "k_dtcbench":
        inferred["split"] = {"value": "test", "basis": "k_dtcbench.py fixed load_dataset split"}
        recorded["limit"] = extra.get("limit") if "limit" in extra else None
    elif benchmark_key == "k_mmbench":
        inferred["split"] = {"value": "dev", "basis": "k_mmbench.py fixed load_dataset split"}
        if "categories_filter" in extra:
            recorded["category_filter"] = extra.get("categories_filter")
        else:
            unknown.append("category_filter")
        if "limit" in extra:
            recorded["limit"] = extra.get("limit")
        else:
            unknown.append("limit")
        if extra.get("sample_mode") is not None:
            recorded["sample_mode"] = extra["sample_mode"]
    elif benchmark_key == "mtvqa_kr":
        split = extra.get("split")
        if split:
            recorded["split"] = split
        else:
            unknown.append("split")
        recorded["category_filter"] = "Korean rows"
        recorded["limit"] = extra.get("limit") if "limit" in extra else None
        recorded["config"] = extra.get("config")
    _add_decoding(config, recorded, unknown)
    return make_protocol(recorded, inferred, unknown), config


def adapt_accuracy(source_dir: Path, benchmark_key: str) -> dict[str, Any]:
    raw_path, summary_path = source_dir / "results.json", source_dir / "summary.json"
    failures: list[str] = []
    warnings: list[str] = []
    try:
        records = load_json(raw_path)
        summary = load_json(summary_path)
    except Exception as exc:
        records, summary = [], {}
        failures.append(f"산출물 읽기 실패: {type(exc).__name__}")
    if not isinstance(records, list) or not isinstance(summary, dict):
        records, summary = [], {}
        failures.append("results.json/summary.json 형식이 올바르지 않음")
    expected = EXPECTED_COUNTS[benchmark_key]
    configured_expected = summary.get("publish_expected_count")
    if benchmark_key == "k_mmbench" and isinstance(configured_expected, int) and configured_expected > 0:
        expected = configured_expected
    aggregate = summarize_records(benchmark_key, records, expected_count=expected)
    counts = aggregate["counts"]
    failures.extend(aggregate["publish_status"]["failures"])
    item_keys, item_key_failure = _accuracy_item_keys(benchmark_key, records)
    if item_key_failure:
        failures.append(item_key_failure)
    item_digest = dataset_item_digest(item_keys) if item_keys else None
    correct = aggregate["correct"]
    if summary.get("total") != counts["attempted"] or summary.get("correct") != correct:
        failures.append("raw 재집계와 summary overall이 일치하지 않음")
    stored_categories = summary.get("by_category")
    if isinstance(stored_categories, dict):
        for category, recalculated in aggregate["by_category"].items():
            stored = stored_categories.get(category) or {}
            if stored.get("correct") != recalculated["correct"] or stored.get("total") != recalculated["total"]:
                failures.append("raw 재집계와 summary category가 일치하지 않음")
                break

    axes = [{"name": "overall", **_fraction(correct, counts["attempted"])}]
    if benchmark_key != "mtvqa_kr":
        axes.extend(
            {"name": f"category:{category}", **_fraction(values["correct"], values["total"])}
            for category, values in aggregate["by_category"].items()
        )
    metrics = {
        "strict": _fraction(correct, counts["attempted"]),
        "conditional": _fraction(correct, counts["measured"]),
        "axes": axes,
    }
    protocol, config = _accuracy_protocol(benchmark_key, summary, source_dir, item_digest)
    extra = config.get("extra") or {}
    variant = "full"
    if benchmark_key == "k_mmbench" and (extra.get("categories_filter") or extra.get("limit")):
        variant = "selected"
    model = str(summary.get("model") or (config.get("model") or {}).get("name") or source_dir.parents[3].name)
    return _base_result(
        benchmark_key=benchmark_key,
        variant=variant,
        model=model,
        source_dir=source_dir,
        source_files=[raw_path, summary_path],
        counts=counts,
        metrics=metrics,
        protocol=protocol,
        completed_at_utc=config.get("timestamp_utc"),
        failures=failures,
        warnings=warnings,
    )


def _kreta_mode(stem: str) -> tuple[str, str]:
    match = re.match(r"^(.*)_(direct|default)$", stem, flags=re.IGNORECASE)
    if not match:
        return stem, "unknown"
    return match.group(1), match.group(2).lower()


def _kreta_axes(rows: list[Mapping[str, Any]], measured_only: bool = True) -> tuple[int, list[dict[str, Any]], dict[str, tuple[int, int]]]:
    correct = 0
    groups: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for row in rows:
        if measured_only and classify_record(row) is not RecordClass.MEASURED:
            continue
        pred = parse_kreta_response(row.get("response"))
        gold = str(row.get("answer", "")).strip().upper()
        ok = pred == gold
        correct += ok
        for name in (
            f"domain:{row.get('category', 'unknown')}",
            f"system:{row.get('topic_difficulty', 'unknown')}",
        ):
            groups[name][1] += 1
            groups[name][0] += ok
    axes = [{"name": name, **_fraction(values[0], values[1])} for name, values in sorted(groups.items())]
    return correct, axes, {name: (values[0], values[1]) for name, values in groups.items()}


def _read_kreta_rows(jsonl_path: Path, failures: list[str]) -> list[dict[str, Any]]:
    """JSONL을 읽고 실패 전까지 읽은 행과 실패 사유를 남긴다."""
    rows: list[dict[str, Any]] = []
    try:
        with jsonl_path.open(encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    value = json.loads(line)
                    if not isinstance(value, dict):
                        raise ValueError("JSONL row is not an object")
                    rows.append(value)
    except Exception as exc:
        failures.append(f"JSONL 읽기 실패: {type(exc).__name__}")
    return rows


def _kreta_upstream_accuracy(jsonl_path: Path, summary_path: Path, warnings: list[str]) -> Any:
    """상류 비교값을 읽고 source 격리 경고를 추가한다."""
    try:
        all_summaries = load_json(summary_path)
        stored = all_summaries.get(jsonl_path.stem) if isinstance(all_summaries, dict) else None
    except Exception:
        stored = None
    upstream_accuracy = stored.get("overall_accuracy") if isinstance(stored, dict) else None
    if not isinstance(stored, dict):
        warnings.append("상류 results.json 비교값 없음 — raw 독립 재채점만 사용")
    elif list(all_summaries) != [jsonl_path.stem]:
        warnings.append("상류 results.json에 다른 source key가 함께 있음 — 채점에는 사용하지 않음")

    return upstream_accuracy


def adapt_kreta(jsonl_path: Path) -> dict[str, Any]:
    source_dir = jsonl_path.parent
    failures: list[str] = []
    warnings: list[str] = []
    rows = _read_kreta_rows(jsonl_path, failures)
    aggregate = summarize_records(
        "kreta", rows, expected_count=EXPECTED_COUNTS["kreta"],
        verify_stored_prediction=True,
    )
    counts = aggregate["counts"]
    counts["no_answer"] = aggregate["no_answer"]
    failures.extend(aggregate["publish_status"]["failures"])
    warnings.extend(aggregate["warnings"])
    ids = [row.get("id") for row in rows]
    if any(value is None for value in ids) or len(set(ids)) != len(ids):
        failures.append("id가 누락되었거나 중복됨")
    item_digest = dataset_item_digest(str(value) for value in ids) if ids and all(value is not None for value in ids) else None
    correct, group_axes, groups = _kreta_axes(rows)
    counts["correct_measured"] = correct

    summary_path = source_dir / "results.json"
    upstream_accuracy = _kreta_upstream_accuracy(jsonl_path, summary_path, warnings)
    model, mode = _kreta_mode(jsonl_path.stem)

    config_path = source_dir / "run_config.json"
    try:
        config = load_json(config_path)
    except Exception:
        config = {}
    protocol = _kreta_protocol(config, mode, item_digest, rows)
    metrics = {
        "strict": _fraction(correct, counts["attempted"]),
        "conditional": _fraction(correct, counts["measured"]),
        "axes": [{"name": "overall", **_fraction(correct, counts["attempted"])}] + group_axes,
    }
    result = _base_result(
        benchmark_key="kreta",
        variant=mode,
        model=model,
        source_dir=source_dir,
        source_files=[jsonl_path, summary_path, config_path],
        counts=counts,
        metrics=metrics,
        protocol=protocol,
        completed_at_utc=None,  # pre-run run_config timestamp is forbidden by contract section 6
        failures=failures,
        warnings=warnings,
    )
    result["no_answer_rate"] = _fraction(aggregate["no_answer"], counts["attempted"])
    result["upstream_comparison"] = {
        "upstream_accuracy": upstream_accuracy,
        "parser_disagreement_rows": aggregate["stored_prediction_mismatches"],
        "disagreement_ours_empty": aggregate["disagreement_ours_empty"],
        "disagreement_different_choice": aggregate["disagreement_different_choice"],
        "note": "상류 파생 필드는 채점 근거로 쓰지 않음",
    }
    return result
