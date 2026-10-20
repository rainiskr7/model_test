"""입력: 저장 행·manifest 또는 반복별 점수. 출력: 문항·이미지 점수와 반복 평균(순수)."""

from math import fsum, isfinite

from shared.multimodal.rescore.kmmbench_circular import METRIC as CIRCULAR_METRIC
from shared.multimodal.rescore.kmmbench_circular import score as circular_score
from shared.multimodal.rescore.manifest import record_issues, validate_manifest
from shared.multimodal.rescore.mtvqa_lmms import METRIC as MTVQA_METRIC
from shared.multimodal.rescore.mtvqa_lmms import score as mtvqa_score

METRICS = {"k_dtcbench": "kdtc_stored_judgement",
           "k_mmbench": CIRCULAR_METRIC, "mtvqa_kr": MTVQA_METRIC}


def score_items(bench, rows, manifest):
    """벤치 행을 검증해 명시된 지표의 문항 점수로 변환한다."""
    validate_manifest(manifest)
    if bench not in METRICS or manifest["benchmark"] != bench:
        raise ValueError("benchmark/manifest mismatch")
    upstream = None
    if bench in ("k_mmbench", "mtvqa_kr"):
        result = (circular_score if bench == "k_mmbench" else mtvqa_score)(rows, manifest)
        if not result["accepted"]:
            raise ValueError("rescore rejected records")
        items = result["group_scores" if bench == "k_mmbench" else "item_scores"]
        upstream = result["upstream"]
    else:
        if record_issues(rows, manifest):
            raise ValueError("records differ from manifest")
        if any(type(row.get("correct")) is not bool for row in rows):
            raise ValueError("boolean correct required")
        items = [{"key": str(row["index"]),
                  "cluster": manifest["items"][str(row["index"])]["cluster"],
                  "score": int(row["correct"] and row.get("error") in (None, ""))}
                 for row in rows]
    return {"metric": METRICS[bench], "version": 1, "upstream": upstream,
            "items": [{"key": v["key"], "cluster": v["cluster"], "score": v["score"]}
                      for v in sorted(items, key=lambda v: v["key"])]}


def index_items(items):
    """비어 있지 않은 유일 문항·이미지·[0,1] 점수를 검증하여 map으로 반환한다."""
    indexed = {}
    for item in items:
        key, cluster, score = item["key"], item["cluster"], item["score"]
        if not isinstance(key, str) or not key or key in indexed:
            raise ValueError("empty/duplicate item key")
        if not isinstance(cluster, str) or not cluster:
            raise ValueError("invalid image cluster")
        if type(score) not in (int, float) or not isfinite(score) or not 0 <= score <= 1:
            raise ValueError("invalid item score")
        indexed[key] = item
    if not indexed:
        raise ValueError("empty item set")
    return indexed


def average_runs(runs):
    """동일 지표·문항·이미지인 반복들을 문항별 산술 평균으로 합친다."""
    if not runs:
        raise ValueError("empty repetitions")
    reference = runs[0]
    indexed = [index_items(run["items"]) for run in runs]
    first = indexed[0]
    for run, items in zip(runs, indexed):
        if any(run.get(k) != reference.get(k) for k in ("metric", "version", "upstream")):
            raise ValueError("repetition metric mismatch")
        if items.keys() != first.keys():
            raise ValueError("repetition item set mismatch")
        if any(items[k]["cluster"] != first[k]["cluster"] for k in first):
            raise ValueError("repetition cluster mismatch")
    return {**{k: reference[k] for k in ("metric", "version", "upstream")},
            "repetitions": len(runs),
            "items": [{"key": k, "cluster": first[k]["cluster"],
                       "score": fsum(sorted(v[k]["score"] for v in indexed)) / len(runs)}
                      for k in sorted(first)]}
