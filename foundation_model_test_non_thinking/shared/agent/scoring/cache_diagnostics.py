"""Annotate-only cache-miss classification for saved Ko-AgentBench runs.

This module never serves a fixture and never changes tool-call results.  It
reconstructs the frozen cache key from the catalog, indexes the recorded
fixtures, and adds diagnostics to an already-computed scoring summary.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


BENCHMARK_SHA = "1174fedd9fa1c7177baa0cbff039a765c9b14d02"
BUCKETS = (
    "exact",
    "presentation_sibling",
    "semantic_mismatch",
    "query_absent",
    "signature_mismatch",
    "tool_absent",
    "unclassified",
)

# Frozen against Ko-AgentBench SHA 1174fedd. Revisit every entry when that pin
# moves. A field is presentation-only only when the catalog contract proves it
# cannot alter result membership or cardinality. Aladin cover changes only the
# cover-image size, output changes only XML/JSON encoding, and opt_result adds
# response fields. Pagination, result-count, sort, filters, coordinates, and
# radius are semantic. Sort is conservative because every affected endpoint
# returns a bounded page, so reordering can change which entities appear.
PRESENTATION_FIELDS: Dict[str, frozenset[str]] = {
    "ItemSearch_aladin": frozenset({"cover", "output", "opt_result"}),
    "ItemList_aladin": frozenset({"cover", "output"}),
    "ItemLookup_aladin": frozenset({"cover", "output", "opt_result"}),
}

# Primary request identity is pinned per tool. Matching identity plus a change
# to any non-presentation argument is a semantic mismatch. Empty tuples denote
# singleton collection endpoints that have no caller-selected entity identity.
IDENTITY_FIELDS: Dict[str, Tuple[str, ...]] = {
    "Directions_naver": ("start", "goal"),
    "StockPrice_ls": ("shcode",),
    "MarketIndex_ls": ("jisu",),
    "SectorStock_ls": ("tmcode",),
    "OrderBook_ls": ("shcode",),
    "StockTrades_ls": ("shcode",),
    "StockPrice_kis": ("symbol",),
    "USStockPrice_kis": ("symbol",),
    "StockChart_kis": ("symbol", "period"),
    "CryptoPrice_bithumb": ("markets",),
    "OrderBook_bithumb": ("markets",),
    "CryptoCandle_bithumb": ("time", "market", "unit", "to"),
    "MarketList_bithumb": (),
    "CryptoPrice_upbit": ("symbol", "quote"),
    "MarketList_upbit": ("quote",),
    "CryptoCandle_upbit": ("symbol", "quote", "candle_type", "unit", "to"),
    "WebSearch_naver": ("query",),
    "BlogSearch_naver": ("query",),
    "NewsSearch_naver": ("query",),
    "WebSearch_daum": ("query",),
    "VideoSearch_daum": ("query",),
    "ItemSearch_aladin": ("query",),
    "ItemList_aladin": ("query_type",),
    "ItemLookup_aladin": ("item_id", "item_id_type"),
    "PlaceSearch_kakao": ("keyword",),
    "AddressToCoord_kakao": ("address",),
    "CategorySearch_kakao": ("category",),
    "CoordToAddress_kakao": ("latitude", "longitude"),
    "POISearch_tmap": ("searchKeyword",),
    "Geocoding_tmap": ("city_do", "gu_gun", "dong"),
    "CategorySearch_tmap": ("categories",),
    "CarRoute_tmap": ("startX", "startY", "endX", "endY"),
    "WalkRoute_tmap": ("startX", "startY", "endX", "endY"),
}

CACHE_MISS_RE = re.compile(r"Pseudo-API\(read\): cache miss\b", re.IGNORECASE)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def tool_signature(description: str, parameters_schema: Mapping[str, Any]) -> str:
    payload = {"description": description, "parameters": parameters_schema or {}}
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def build_cache_key(tool_name: str, normalized_args: Mapping[str, Any], signature: str) -> str:
    payload = {"tool": tool_name, "args": normalized_args, "sig": signature}
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def normalize_args(
    tool_name: str, raw_args: Mapping[str, Any], parameters_schema: Mapping[str, Any]
) -> Dict[str, Any]:
    """Mirror the pinned benchmark normalizer without importing the package."""

    normalized = dict(raw_args or {})
    if tool_name == "StockPrice_ls":
        if "shcode" not in normalized and "symbol" in normalized:
            normalized["shcode"] = normalized.pop("symbol")
        if "exchgubun" not in normalized:
            normalized["exchgubun"] = "K"

    properties = (parameters_schema or {}).get("properties", {}) or {}
    for name, definition in properties.items():
        if name not in normalized and "default" in definition:
            normalized[name] = definition["default"]

    for name, definition in properties.items():
        if name not in normalized:
            continue
        value = normalized[name]
        kind = definition.get("type")
        try:
            if kind == "integer" and not isinstance(value, int):
                normalized[name] = int(value)
            elif kind == "number" and not isinstance(value, (int, float)):
                normalized[name] = float(value)
            elif kind == "boolean" and isinstance(value, str):
                if value.lower() in ("true", "1", "yes"):
                    normalized[name] = True
                elif value.lower() in ("false", "0", "no"):
                    normalized[name] = False
            elif kind == "string" and not isinstance(value, str):
                normalized[name] = str(value)
        except Exception:
            pass

    normalized = {name: value for name, value in normalized.items() if name in properties}
    return {name: normalized[name] for name in sorted(normalized)}


def load_catalog(catalog_path: Path) -> Dict[str, Dict[str, Any]]:
    """Read literal descriptions and schemas from TOOL_CATALOG without imports."""

    tree = ast.parse(Path(catalog_path).read_text(encoding="utf-8"))
    catalog_node = next(
        (
            node.value
            for node in tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "TOOL_CATALOG"
            and isinstance(node.value, ast.Dict)
        ),
        None,
    )
    if catalog_node is None:
        raise ValueError(f"TOOL_CATALOG literal not found: {catalog_path}")

    catalog: Dict[str, Dict[str, Any]] = {}
    for key_node, entry_node in zip(catalog_node.keys, catalog_node.values):
        if not isinstance(entry_node, (ast.Tuple, ast.List)) or len(entry_node.elts) < 4:
            continue
        try:
            tool_name = ast.literal_eval(key_node)
            description = ast.literal_eval(entry_node.elts[2])
            parameters_schema = ast.literal_eval(entry_node.elts[3])
        except (ValueError, TypeError, SyntaxError):
            continue
        if not isinstance(tool_name, str) or not isinstance(description, str):
            continue
        if not isinstance(parameters_schema, dict):
            continue
        catalog[tool_name] = {
            "description": description,
            "parameters_schema": parameters_schema,
            "signature": tool_signature(description, parameters_schema),
        }
    return catalog


def make_catalog_entry(description: str, parameters_schema: Mapping[str, Any]) -> Dict[str, Any]:
    """Small public helper for fully synthetic offline tests."""

    schema = dict(parameters_schema)
    return {
        "description": description,
        "parameters_schema": schema,
        "signature": tool_signature(description, schema),
    }


def load_fixture_index(
    cache_dir: Path, catalog: Mapping[str, Mapping[str, Any]]
) -> Dict[str, List[Dict[str, Any]]]:
    """Load fixtures in stable key order and mark current-signature reachability."""

    index: Dict[str, List[Dict[str, Any]]] = {}
    for path in sorted(Path(cache_dir).glob("*/*/*.json"), key=lambda item: item.as_posix()):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            continue
        if not isinstance(record, dict):
            continue
        tool_name = record.get("tool") or path.parents[1].name
        if not isinstance(tool_name, str):
            continue
        key = record.get("key") or path.stem
        if not isinstance(key, str):
            continue
        args = record.get("input_params")
        if not isinstance(args, dict):
            args = record.get("raw_args") if isinstance(record.get("raw_args"), dict) else {}
        spec = catalog.get(tool_name)
        reachable = False
        if spec is not None:
            expected = build_cache_key(tool_name, args, str(spec["signature"]))
            reachable = expected == key
        index.setdefault(tool_name, []).append(
            {"key": key, "args": args, "reachable": reachable}
        )
    for fixtures in index.values():
        fixtures.sort(key=lambda fixture: fixture["key"])
    return index


def _is_cache_miss(call: Mapping[str, Any]) -> bool:
    return bool(CACHE_MISS_RE.search(str(call.get("error") or "")))


def _identity_value(tool_name: str, args: Mapping[str, Any]) -> Optional[Tuple[Any, ...]]:
    fields = IDENTITY_FIELDS.get(tool_name)
    if fields is None:
        return None
    if fields and not any(field in args for field in fields):
        return None
    return tuple(args.get(field) for field in fields)


def _semantic_projection(tool_name: str, args: Mapping[str, Any]) -> Dict[str, Any]:
    presentation = PRESENTATION_FIELDS.get(tool_name, frozenset())
    return {name: value for name, value in args.items() if name not in presentation}


def classify_call(
    call: Mapping[str, Any],
    catalog: Mapping[str, Mapping[str, Any]],
    fixture_index: Mapping[str, Sequence[Mapping[str, Any]]],
) -> Dict[str, Any]:
    """Classify one saved call; selected fixture keys use a stable total order."""

    tool_name = call.get("tool_name") or call.get("tool")
    raw_args = call.get("arguments")
    if not isinstance(raw_args, dict):
        raw_args = call.get("args") if isinstance(call.get("args"), dict) else {}
    cache_miss = _is_cache_miss(call)
    result = {"bucket": "unclassified", "fixture_key": None, "cache_miss": cache_miss}
    if not isinstance(tool_name, str):
        return result

    fixtures = list(fixture_index.get(tool_name, ()))
    if tool_name not in catalog:
        if fixtures:
            result.update(
                bucket="signature_mismatch",
                fixture_key=min(fixture["key"] for fixture in fixtures),
            )
        else:
            result["bucket"] = "tool_absent"
        return result

    spec = catalog[tool_name]
    normalized = normalize_args(tool_name, raw_args, spec["parameters_schema"])
    requested_key = build_cache_key(tool_name, normalized, str(spec["signature"]))
    reachable = [fixture for fixture in fixtures if fixture.get("reachable") is True]

    exact = [fixture for fixture in reachable if fixture.get("key") == requested_key]
    if exact:
        result.update(bucket="exact", fixture_key=min(fixture["key"] for fixture in exact))
        return result
    if reachable:
        requested_semantic = _semantic_projection(tool_name, normalized)
        presentation_candidates = [
            fixture
            for fixture in reachable
            if fixture.get("args") != normalized
            and _semantic_projection(tool_name, fixture.get("args") or {})
            == requested_semantic
        ]
        if presentation_candidates:
            result["bucket"] = "presentation_sibling"
            result["fixture_key"] = min(
                fixture["key"] for fixture in presentation_candidates
            )
            return result

        identity = _identity_value(tool_name, normalized)
        if identity is None:
            return result
        same_identity_reachable = [
            fixture
            for fixture in reachable
            if _identity_value(tool_name, fixture.get("args") or {}) == identity
        ]
        semantic_candidates = [
            fixture
            for fixture in same_identity_reachable
            if _semantic_projection(tool_name, fixture.get("args") or {})
            != requested_semantic
        ]
        if semantic_candidates:
            result["bucket"] = "semantic_mismatch"
            result["fixture_key"] = min(
                fixture["key"] for fixture in semantic_candidates
            )
            return result
        if not same_identity_reachable:
            result["bucket"] = "query_absent"
        return result

    if fixtures:
        result["bucket"] = "signature_mismatch"
        result["fixture_key"] = min(fixture["key"] for fixture in fixtures)
        return result

    result["bucket"] = "tool_absent"
    return result


def _calls(level_data: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    tasks = level_data.get("results")
    if not isinstance(tasks, list):
        tasks = level_data.get("tasks")
    if not isinstance(tasks, list):
        return
    for task in tasks:
        if not isinstance(task, dict):
            continue
        calls = task.get("tool_calls")
        if not isinstance(calls, list):
            continue
        for call in calls:
            if isinstance(call, dict):
                yield call


def _empty_counts() -> Dict[str, int]:
    return {bucket: 0 for bucket in BUCKETS}


def _summarize_classifications(classifications: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    counts = _empty_counts()
    miss_counts = _empty_counts()
    total_calls = 0
    cache_misses = 0
    for classification in classifications:
        total_calls += 1
        bucket = classification.get("bucket")
        assigned = bucket if bucket in counts else "unclassified"
        counts[assigned] += 1
        is_cache_miss = classification.get("cache_miss") is True
        cache_misses += is_cache_miss
        if is_cache_miss:
            miss_counts[assigned] += 1
    return {
        "total_calls": total_calls,
        "cache_misses": cache_misses,
        "miss_rate": (cache_misses / total_calls) if total_calls else 0.0,
        "counts": counts,
        "miss_counts": miss_counts,
    }


def _discover_benchmark_paths(results_dir: Path) -> Tuple[Optional[Path], Optional[Path]]:
    candidates: List[Path] = []
    base = os.environ.get("MODEL_TEST_BASE")
    if base:
        candidates.append(Path(base))
    candidates.extend([Path(results_dir), *Path(results_dir).parents])
    seen = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        bench = resolved / "data" / "Ko-AgentBench" / "bench"
        cache_dir = bench / "cache"
        catalog_path = bench / "tools" / "tool_catalog.py"
        if cache_dir.is_dir() and catalog_path.is_file():
            return cache_dir, catalog_path
    return None, None


def build_cache_diagnostics(
    loaded: Mapping[str, Mapping[str, Any]],
    results_dir: Path,
    *,
    catalog: Optional[Mapping[str, Mapping[str, Any]]] = None,
    fixture_index: Optional[Mapping[str, Sequence[Mapping[str, Any]]]] = None,
) -> Dict[str, Any]:
    """Build the score-neutral per-level and whole-run diagnostic block."""

    available = catalog is not None and fixture_index is not None
    reason = None
    if not available:
        cache_dir, catalog_path = _discover_benchmark_paths(results_dir)
        if cache_dir is None or catalog_path is None:
            catalog = {}
            fixture_index = {}
            reason = "pinned fixture set or tool catalog not found"
        else:
            catalog = load_catalog(catalog_path)
            fixture_index = load_fixture_index(cache_dir, catalog)
            available = True

    assert catalog is not None
    assert fixture_index is not None
    by_level: Dict[str, Dict[str, Any]] = {}
    all_classifications: List[Dict[str, Any]] = []
    for level in sorted(loaded):
        classifications = [
            classify_call(call, catalog, fixture_index) for call in _calls(loaded[level])
        ]
        by_level[level] = _summarize_classifications(classifications)
        all_classifications.extend(classifications)

    diagnostic = {
        "mode": "annotate_only",
        "serves_relaxed_matches": False,
        "benchmark_sha": BENCHMARK_SHA,
        "available": available,
        "overall": _summarize_classifications(all_classifications),
        "by_level": by_level,
    }
    if reason:
        diagnostic["unavailable_reason"] = reason
    return diagnostic
