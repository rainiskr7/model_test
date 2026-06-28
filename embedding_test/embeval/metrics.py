"""순위 품질 지표 — repr(dense/sparse/hybrid) 검색 평가용 순수 함수.

rerankeval/metrics.py 의 순수 함수를 그대로 복사(각 하니스 자기완결 정책). 외부 의존 없음.

규약:
  ranking : 점수 내림차순 doc_id 리스트(상위가 앞).
  qrels   : {doc_id: gain}. gain>0 이면 관련 문서. binary 면 gain∈{0,1}.
"""

from __future__ import annotations

import math


def _gain(qrels: dict, doc_id) -> float:
    return float(qrels.get(doc_id, 0.0))


def dcg_at_k(ranking: list, qrels: dict, k: int) -> float:
    total = 0.0
    for i, doc_id in enumerate(ranking[:k]):
        g = _gain(qrels, doc_id)
        if g > 0:
            total += (2.0 ** g - 1.0) / math.log2(i + 2)
    return total


def ndcg_at_k(ranking: list, qrels: dict, k: int) -> float:
    ideal = sorted((g for g in qrels.values() if g > 0), reverse=True)
    idcg = 0.0
    for i, g in enumerate(ideal[:k]):
        idcg += (2.0 ** g - 1.0) / math.log2(i + 2)
    if idcg == 0.0:
        return 0.0
    return dcg_at_k(ranking, qrels, k) / idcg


def mrr(ranking: list, qrels: dict, k: int | None = None) -> float:
    seq = ranking if k is None else ranking[:k]
    for i, doc_id in enumerate(seq):
        if _gain(qrels, doc_id) > 0:
            return 1.0 / (i + 1)
    return 0.0


def precision_at_k(ranking: list, qrels: dict, k: int) -> float:
    if k <= 0:
        return 0.0
    hits = sum(1 for doc_id in ranking[:k] if _gain(qrels, doc_id) > 0)
    return hits / k


def hit_rate_at_1(ranking: list, qrels: dict) -> float:
    return 1.0 if ranking and _gain(qrels, ranking[0]) > 0 else 0.0


def recall_at_k(ranking: list, qrels: dict, k: int) -> float:
    total_rel = sum(1 for g in qrels.values() if g > 0)
    if total_rel == 0:
        return 0.0
    hits = sum(1 for doc_id in ranking[:k] if _gain(qrels, doc_id) > 0)
    return hits / total_rel


def query_metrics(ranking: list, qrels: dict, ks: tuple[int, ...] = (1, 5, 10)) -> dict:
    out: dict[str, float] = {"mrr": mrr(ranking, qrels), "hit_rate@1": hit_rate_at_1(ranking, qrels)}
    for k in ks:
        out[f"ndcg@{k}"] = ndcg_at_k(ranking, qrels, k)
        out[f"precision@{k}"] = precision_at_k(ranking, qrels, k)
        out[f"recall@{k}"] = recall_at_k(ranking, qrels, k)
    return out


def mean_metrics(per_query: list[dict]) -> dict:
    if not per_query:
        return {}
    keys = per_query[0].keys()
    return {kk: sum(d[kk] for d in per_query) / len(per_query) for kk in keys}
