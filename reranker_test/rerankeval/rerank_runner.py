"""2-stage 리랭킹 평가(retrieval 태스크) — 계획안 1.3 A/B + 3-2.

흐름: retrieval 데이터 로드 → frozen 1차 후보(top-N) → 리랭커 재채점
     → baseline(1차 순서) vs reranked 지표 비교(A/B) → 결과 저장.

candidate 수 민감도(계획안 3·5절): SETTINGS.candidate_top_ns(20/50/100) 각각에 대해 측정.
재시작: 결과 JSON 이 이미 있으면 건너뜀(overwrite 로 강제 재실행).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from evalcommon import free_model as _free, set_seed as _set_seed
from evalcommon import results as _results

from .config import SETTINGS, TaskSpec, model_full_name, model_backend, resolve_spec
from . import metrics as M


def _result_path(spec: TaskSpec, reranker_key: str, embedder_key: str,
                 mode: str, top_n: int) -> Path:
    safe = spec.name.replace("/", "_")
    return (Path(SETTINGS.results_dir) / "rerank" /
            f"{safe}__{reranker_key}__emb-{embedder_key}__{mode}__top{top_n}.json")


def evaluate_retrieval_task(spec: TaskSpec, reranker, reranker_key: str,
                            embedder_key: str, mode: str,
                            *, overwrite: bool = False) -> list[dict]:
    """한 retrieval 태스크를 모든 top_n 에 대해 2-stage 평가. 결과 dict 리스트 반환."""
    from .datasets import load_retrieval_data
    from .firststage import build_candidates

    data = load_retrieval_data(spec)
    corpus, qrels = data["corpus"], data["qrels"]
    queries = data["queries"]
    max_n = max(SETTINGS.candidate_top_ns)

    # 최대 N 으로 후보를 한 번만 만들고, 작은 N 은 슬라이스(동결 일관성)
    cand_full = build_candidates(spec, data, embedder_key, max_n, overwrite=overwrite)

    out = []
    for top_n in SETTINGS.candidate_top_ns:
        rp = _result_path(spec, reranker_key, embedder_key, mode, top_n)
        if rp.exists() and not overwrite:
            print(f"[rerank] 건너뜀(재개): {rp.name}")
            out.append(json.loads(rp.read_text()))
            continue

        base_pq, rer_pq = [], []
        cand_recalls = []     # 후보 집합 recall 상한(정답이 top_n 안에 있는가)
        rerank_latencies = []  # 쿼리당 rerank 시간(초)
        for qid, rels in qrels.items():
            cand = cand_full.get(qid, [])[:top_n]
            if not cand:
                continue
            cand_ids = [d for d, _ in cand]
            baseline_ranking = cand_ids  # 1차 점수 내림차순(이미 정렬됨)

            # 후보 ceiling(codex 검토 #3): 정답이 후보 top_n 안에 얼마나 들어왔나.
            # 정답이 후보에 없으면 리랭커가 절대 복구 불가 → 이 상한을 분리 기록.
            cand_recalls.append(M.recall_at_k(baseline_ranking, rels, top_n))

            docs = [corpus[d] for d in cand_ids]
            t0 = time.perf_counter()
            scores = reranker.score(queries[qid], docs)
            rerank_latencies.append(time.perf_counter() - t0)

            reranked_ranking = [d for d, _ in
                                sorted(zip(cand_ids, scores), key=lambda x: -x[1])]

            base_pq.append(M.query_metrics(baseline_ranking, rels, SETTINGS.eval_ks))
            rer_pq.append(M.query_metrics(reranked_ranking, rels, SETTINGS.eval_ks))

        rec = {
            "task": spec.name, "kind": "retrieval", "domain": spec.domain,
            "reranker": reranker_key, "embedder": embedder_key, "mode": mode,
            "top_n": top_n, "n_queries": len(base_pq),
            "primary": f"{spec.primary_metric}@{spec.primary_k}"
                       if spec.primary_metric in ("ndcg", "precision") else spec.primary_metric,
            "candidate_recall": (sum(cand_recalls) / len(cand_recalls)) if cand_recalls else 0.0,
            "baseline": M.mean_metrics(base_pq),
            "reranked": M.mean_metrics(rer_pq),
            "rerank_latency": M.percentiles([x * 1000 for x in rerank_latencies]),  # ms
            "delta": _delta(M.mean_metrics(base_pq), M.mean_metrics(rer_pq)),
        }
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(json.dumps(rec, ensure_ascii=False, indent=2))
        print(f"[rerank] {rp.name}: Δ{rec['primary']}="
              f"{rec['delta'].get(_primary_key(spec), 0):+.4f}")
        if _results.session_active():
            _emit_rerank_summary(rec, reranker_key)
        out.append(rec)
    return out


def _emit_rerank_summary(rec: dict, reranker_key: str) -> None:
    """2-stage A/B rec → model_test 규약 summary.json (track='rerank')."""
    pk = rec.get("primary")
    model_full = model_full_name(reranker_key)
    backend, _ = model_backend(reranker_key)
    spec = resolve_spec(reranker_key)
    score = rec.get("reranked", {}).get(pk)
    base = rec.get("baseline", {}).get(pk)
    extra = {
        "kind": "retrieval", "backend": backend, "reranker_backend": spec.backend,
        "mode": rec.get("mode"), "top_n": rec.get("top_n"), "embedder": rec.get("embedder"),
        "candidate_recall": rec.get("candidate_recall"),
        "baseline": rec.get("baseline"), "rerank_latency": rec.get("rerank_latency"),
    }
    run_cfg = _results.build_run_config(
        benchmark=rec.get("task"), model_full_name=model_full,
        seed=SETTINGS.seed, precision=SETTINGS.precision,
        batch_size=SETTINGS.rerank_batch_size, max_seq_length=SETTINGS.max_doc_len,
        prompt_mode=rec.get("mode"),
        eval_script_path=str(Path(__file__).resolve()), extra=extra)
    payload = {
        "benchmark": rec.get("task"), "model": model_full,
        "total": rec.get("n_queries", 0), "total_kind": "queries",
        "metric": pk, "score": round(float(score), 6) if score is not None else 0.0,
        "baseline_score": round(float(base), 6) if base is not None else None,
        "delta": round(float(score - base), 6) if (score is not None and base is not None) else None,
        "prompt_mode": rec.get("mode"), "kind": "retrieval", "run_config": run_cfg,
    }
    bench = f"{rec.get('task')}__{rec.get('mode')}__top{rec.get('top_n')}__emb-{rec.get('embedder')}"
    _results.write_summary("rerank", bench, payload, model_full_name=model_full)


def _primary_key(spec: TaskSpec) -> str:
    if spec.primary_metric in ("ndcg", "precision"):
        return f"{spec.primary_metric}@{spec.primary_k}"
    return spec.primary_metric


def _delta(base: dict, rer: dict) -> dict:
    return {k: rer.get(k, 0.0) - base.get(k, 0.0) for k in rer}


def run_retrieval_tasks(task_specs: list[TaskSpec], reranker_keys: list[str],
                        embedder_key: str, modes: list[str], *,
                        overwrite: bool = False) -> None:
    from .rerankers import load_reranker
    _set_seed(SETTINGS.seed)  # 재현성(계획안 6절)
    retr = [s for s in task_specs if s.kind == "retrieval"]
    for rk in reranker_keys:
        for mode in modes:
            print(f"\n>>> [rerank] reranker={rk} mode={mode} emb={embedder_key}")
            reranker = load_reranker(rk, mode)
            try:
                for spec in retr:
                    evaluate_retrieval_task(spec, reranker, rk, embedder_key, mode,
                                            overwrite=overwrite)
            finally:
                _free(reranker)  # 예외에도 해제(누수 방지)


