"""순위 품질 지표 — 계획안 4절. 순수 함수(외부 의존 없음) → 단위 테스트 대상.

공통 입력 규약:
  ranking : 점수 내림차순으로 정렬된 doc_id 리스트 (상위가 앞).
  qrels   : {doc_id: gain} 그레이드 관련도. gain>0 이면 관련 문서로 간주.
            binary 라벨이면 gain ∈ {0,1}.

지표(계획안 1.2 / 4절):
  - nDCG@k : 상위 k 순서 품질(그레이드 gain 반영). 표준 주 지표.
  - MRR    : 첫 관련 문서 순위의 역수.
  - Precision@k : 상위 k 중 관련 문서 비율.
  - Hit Rate@1  : 상위 1개가 관련 문서면 1, 아니면 0(쿼리 단위 → 평균이 비율).
  - Recall@k    : (보조) 1차 후보가 정답을 얼마나 담았는가 = 리랭커 성능 상한.
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
            total += (2.0 ** g - 1.0) / math.log2(i + 2)  # rank i(0-base) → 위치 i+1
    return total


def ndcg_at_k(ranking: list, qrels: dict, k: int) -> float:
    ideal = sorted((g for g in qrels.values() if g > 0), reverse=True)
    idcg = 0.0
    for i, g in enumerate(ideal[:k]):
        idcg += (2.0 ** g - 1.0) / math.log2(i + 2)
    if idcg == 0.0:
        return 0.0  # 관련 문서가 없는 쿼리는 0
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
    """상위 k 안에 든 관련 문서 / 전체 관련 문서. 1차 후보 recall 상한 측정용."""
    total_rel = sum(1 for g in qrels.values() if g > 0)
    if total_rel == 0:
        return 0.0
    hits = sum(1 for doc_id in ranking[:k] if _gain(qrels, doc_id) > 0)
    return hits / total_rel


# 쿼리별 지표를 한 번에 계산(러너에서 사용) -------------------------------------- #
def query_metrics(ranking: list, qrels: dict, ks: tuple[int, ...] = (1, 5, 10)) -> dict:
    out: dict[str, float] = {"mrr": mrr(ranking, qrels), "hit_rate@1": hit_rate_at_1(ranking, qrels)}
    for k in ks:
        out[f"ndcg@{k}"] = ndcg_at_k(ranking, qrels, k)
        out[f"precision@{k}"] = precision_at_k(ranking, qrels, k)
        out[f"recall@{k}"] = recall_at_k(ranking, qrels, k)
    return out


def mean_metrics(per_query: list[dict]) -> dict:
    """쿼리별 지표 dict 리스트 → 평균(매크로). 빈 입력은 {}."""
    if not per_query:
        return {}
    keys = per_query[0].keys()
    return {kk: sum(d[kk] for d in per_query) / len(per_query) for kk in keys}


def percentiles(values: list[float], ps: tuple[int, ...] = (50, 95, 99)) -> dict:
    """latency 분포(계획안 3절). 선형보간 없는 nearest-rank 방식(결정적)."""
    if not values:
        return {f"p{p}": 0.0 for p in ps}
    s = sorted(values)
    out = {}
    for p in ps:
        # nearest-rank: ceil(p/100 * N) 번째(1-base)
        idx = max(1, math.ceil(p / 100.0 * len(s))) - 1
        out[f"p{p}"] = s[idx]
    return out
