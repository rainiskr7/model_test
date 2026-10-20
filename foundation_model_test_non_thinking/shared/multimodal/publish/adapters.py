"""Offline adapters for the seven multimodal benchmark families."""

from __future__ import annotations

import json
import math
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from shared.multimodal.publish.classify import classify_record
from shared.multimodal.publish.adapters_protocol import (
    _add_decoding, _dataset_revision, _add_dataset_provenance,
    _kreta_protocol, _judge_protocol,
)
from shared.multimodal.publish.schema import (
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


# Keep legacy public/private imports and shared constant objects available here.
from shared.multimodal.publish.adapters_common import (
    EXPECTED_COUNTS, BENCHMARK_IDS, BENCHMARK_KEYS,
    load_json, _fraction, _counts, _run_config, _base_result, _same_metric,
)
from shared.multimodal.publish.adapters_accuracy import (
    _score_classified_records, summarize_records, parse_kreta_response,
    _choice, _normalize_answer, _mtvqa_match, _accuracy_item_keys,
    _accuracy_protocol, adapt_accuracy, _kreta_mode, _kreta_axes,
    _read_kreta_rows, _kreta_upstream_accuracy, adapt_kreta,
)
from shared.multimodal.publish.adapters_koffvqa import (
    _session_of, _prediction_session, _aggregate_judge_rows,
    adapt_koffvqa, adapt_koffvqa_judge,
)
from shared.multimodal.publish.adapters_customb import (
    _b3_raw_metrics, adapt_b3, _percentiles, _b4_raw_summary,
    _b4_summary_matches, _aggregate_latency_conditions, adapt_b4,
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
