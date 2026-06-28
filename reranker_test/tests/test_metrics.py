"""순위 지표 검증 — 손계산과 대조(GPU 불필요). 계획안 4절."""

import math

from rerankeval import metrics as M


def test_ndcg_perfect_ranking_is_one():
    qrels = {"a": 3, "b": 2, "c": 1}
    ranking = ["a", "b", "c", "d"]
    assert abs(M.ndcg_at_k(ranking, qrels, 10) - 1.0) < 1e-9


def test_ndcg_known_value_binary():
    # 관련 문서 1개("a")가 2위 → DCG=1/log2(3), IDCG=1/log2(2)=1
    qrels = {"a": 1}
    ranking = ["x", "a", "y"]
    expected = (1.0 / math.log2(3)) / 1.0
    assert abs(M.ndcg_at_k(ranking, qrels, 10) - expected) < 1e-9


def test_ndcg_no_relevant_is_zero():
    assert M.ndcg_at_k(["a", "b"], {}, 10) == 0.0


def test_mrr_first_relevant_rank3():
    assert M.mrr(["x", "y", "a", "b"], {"a": 1}) == 1.0 / 3


def test_mrr_none_relevant():
    assert M.mrr(["x", "y"], {"a": 1}) == 0.0


def test_precision_at_k():
    qrels = {"a": 1, "c": 1}
    assert M.precision_at_k(["a", "b", "c", "d"], qrels, 4) == 0.5
    assert M.precision_at_k(["a", "b", "c", "d"], qrels, 2) == 0.5


def test_hit_rate_at_1():
    assert M.hit_rate_at_1(["a", "b"], {"a": 1}) == 1.0
    assert M.hit_rate_at_1(["b", "a"], {"a": 1}) == 0.0
    assert M.hit_rate_at_1([], {"a": 1}) == 0.0


def test_recall_at_k():
    qrels = {"a": 1, "b": 1, "c": 1}
    assert M.recall_at_k(["a", "b", "x", "y"], qrels, 2) == 2 / 3
    assert M.recall_at_k(["a", "b", "c"], qrels, 10) == 1.0


def test_candidate_recall_ceiling():
    # codex #3: 정답이 후보 top_n 밖이면 recall<1 → 리랭커 복구 불가 상한이 드러나야.
    qrels = {"gold": 1}
    candidates = ["x", "y", "z"]  # gold 없음
    assert M.recall_at_k(candidates, qrels, 3) == 0.0
    candidates2 = ["x", "gold", "z"]
    assert M.recall_at_k(candidates2, qrels, 3) == 1.0


def test_graded_gain_orders_higher_grade_first():
    # gain 3 문서를 1위로 올린 랭킹이 gain 1 을 1위로 둔 것보다 nDCG 높아야
    qrels = {"hi": 3, "lo": 1}
    good = M.ndcg_at_k(["hi", "lo"], qrels, 10)
    bad = M.ndcg_at_k(["lo", "hi"], qrels, 10)
    assert good > bad


def test_percentiles_nearest_rank():
    vals = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    p = M.percentiles(vals, (50, 95, 99))
    assert p["p50"] == 50      # ceil(0.5*10)=5 → idx4 → 50
    assert p["p95"] == 100     # ceil(0.95*10)=10 → idx9 → 100
    assert p["p99"] == 100


def test_percentiles_empty():
    assert M.percentiles([]) == {"p50": 0.0, "p95": 0.0, "p99": 0.0}


def test_mean_metrics():
    pq = [{"ndcg@10": 0.4, "mrr": 1.0}, {"ndcg@10": 0.6, "mrr": 0.5}]
    m = M.mean_metrics(pq)
    assert abs(m["ndcg@10"] - 0.5) < 1e-9 and abs(m["mrr"] - 0.75) < 1e-9
    assert M.mean_metrics([]) == {}
