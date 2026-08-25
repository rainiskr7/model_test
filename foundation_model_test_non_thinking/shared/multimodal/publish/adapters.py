"""Offline adapters for the seven multimodal benchmark families."""

from __future__ import annotations

import json
import math
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from .classify import classify_record
from .schema import (
    COMPARISON_CRITICAL_UNKNOWN,
    KRETA_ANSWER_PARSER_HASH,
    KRETA_ANSWER_PARSER_SPEC,
    KRETA_ANSWER_PARSER_VERSION,
    PublishStatus,
    RecordClass,
    dataset_item_digest,
    make_protocol,
    sha256_file,
)


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


def _add_decoding(config: Mapping[str, Any], recorded: dict[str, Any], unknown: list[str]) -> None:
    decoding = config.get("decoding") or {}
    serving = config.get("serving_constraints")
    removed = set(serving.get("removed_parameters") or []) if isinstance(serving, Mapping) else set()
    for key in ("temperature", "max_tokens", "seed"):
        value = decoding.get(key)
        if key in removed:
            recorded[f"{key}_removed"] = True
        elif value is None:
            unknown.append(key)
        else:
            recorded[key] = value
    if isinstance(serving, Mapping):
        recorded["serving_constraints"] = {
            key: serving.get(key)
            for key in (
                "unsupported_sampling_params",
                "max_output_tokens",
                "force_skip_special_tokens",
                "removed_parameters",
                "skip_special_tokens",
            )
        }
    unknown.extend(("prompt_template_hash", "answer_parser_hash", "image_preprocessing_version"))


def _dataset_revision(config: Mapping[str, Any]) -> Any:
    dataset = config.get("dataset") or {}
    return dataset.get("revision") or dataset.get("git_commit")


def _add_dataset_provenance(config: Mapping[str, Any], recorded: dict[str, Any]) -> None:
    dataset = config.get("dataset")
    if not isinstance(dataset, Mapping):
        return
    recorded["dataset_provenance"] = {
        key: dataset.get(key)
        for key in ("huggingface_id", "revision", "revision_source", "git_repo", "git_commit")
        if key in dataset
    }


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


def adapt_kreta(jsonl_path: Path) -> dict[str, Any]:
    source_dir = jsonl_path.parent
    failures: list[str] = []
    warnings: list[str] = []
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

    model, mode = _kreta_mode(jsonl_path.stem)

    config_path = source_dir / "run_config.json"
    try:
        config = load_json(config_path)
    except Exception:
        config = {}
    recorded: dict[str, Any] = {"benchmark": "KRETA"}
    inferred: dict[str, Any] = {}
    unknown: list[str] = []
    if mode == "unknown":
        unknown.append("mode")
    else:
        recorded["mode"] = mode
        _add_decoding(config, recorded, unknown)
        # KRETA binds its own fixed response parser below; this is known even
        # though the generic helper treats answer parser metadata as absent.
        unknown = [item for item in unknown if item != "answer_parser_hash"]
        if "max_tokens" in unknown:
            unknown.remove("max_tokens")
            inferred["max_tokens"] = {
                "value": 32 if mode == "direct" else 4096,
                "basis": f"legacy run_kreta.sh: {mode} mode default KRETA_MAX_TOKENS",
            }
    recorded["answer_parser_version"] = KRETA_ANSWER_PARSER_VERSION
    recorded["answer_parser_hash"] = KRETA_ANSWER_PARSER_HASH
    _add_dataset_provenance(config, recorded)
    if item_digest:
        recorded["dataset_item_digest"] = item_digest
    else:
        unknown.append("dataset_item_digest")
    splits = {row.get("split") for row in rows if row.get("split") is not None}
    if len(splits) == 1:
        recorded["split"] = next(iter(splits))
    else:
        unknown.append("split")
    if mode == "unknown":
        unknown.extend(("temperature", "seed", "prompt_template_hash", "image_preprocessing_version"))
    protocol = make_protocol(recorded, inferred, unknown)
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
    recorded = {
        "benchmark": "KOFFVQA-judge",
        "judge_model": summary.get("judge_model"),
        "judge_prompt_version": summary.get("judge_prompt_version"),
        "prediction_sha256": recorded_sha,
        "dataset_item_digest": item_digest,
        "limit": (config.get("extra") or {}).get("limit"),
    }
    unknown = [key for key in ("judge_model", "judge_prompt_version") if not recorded.get(key)]
    _add_decoding(config, recorded, unknown)
    if generation_revision:
        recorded["dataset_provenance"] = {"revision": generation_revision}
    if not item_digest:
        unknown.append("dataset_item_digest")
    protocol = make_protocol(recorded, {}, unknown)
    metrics = {
        "axes": [{"name": "rubric", "value": average, "unit": "score/10", "numerator": sum(scores), "denominator": len(scores)}]
    }
    model = str(summary.get("target_model") or (config.get("model") or {}).get("name") or source_dir.parents[3].name)
    return _base_result(
        benchmark_key="koffvqa_api_judge",
        variant="api_judge",
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


def _same_metric(stored: Any, calculated: Any) -> bool:
    if stored is None or calculated is None:
        return stored is None and calculated is None
    if isinstance(stored, bool) or isinstance(calculated, bool):
        return stored is calculated
    if isinstance(stored, (int, float)) and isinstance(calculated, (int, float)):
        return math.isclose(float(stored), float(calculated), rel_tol=1e-12, abs_tol=1e-12)
    return stored == calculated


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


ADAPTERS: dict[str, Callable[[Path], dict[str, Any]]] = {
    "k_dtcbench": lambda path: adapt_accuracy(path, "k_dtcbench"),
    "k_mmbench": lambda path: adapt_accuracy(path, "k_mmbench"),
    "mtvqa_kr": lambda path: adapt_accuracy(path, "mtvqa_kr"),
    "koffvqa": adapt_koffvqa,
    "koffvqa_api_judge": adapt_koffvqa_judge,
    "b3_structured_output": adapt_b3,
    "b4_latency_profile": adapt_b4,
}


def adapt_source(source: Path) -> dict[str, Any]:
    if source.suffix == ".jsonl" and source.parent.name == "kreta":
        return adapt_kreta(source)
    try:
        adapter = ADAPTERS[source.name]
    except KeyError as exc:
        raise ValueError(f"unsupported benchmark source: {source}") from exc
    return adapter(source)
