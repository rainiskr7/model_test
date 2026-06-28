"""Latency & 효율성 측정 — 계획안 3·5절. 품질과 분리 측정.

cross-encoder 는 후보 1개당 forward 1회 → candidate 수에 latency 가 민감.
후보 수(top-N) 별로:
  - P50/P95/P99 latency (쿼리 단위, ms)
  - Throughput (queries/s)
  - Peak VRAM (GB)
→ candidate 수 민감도 곡선(NDCG 는 rerank_runner 결과와 aggregate 에서 결합).
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

from evalcommon import free_model as _free, set_seed as _set_seed
from evalcommon import results as _results

from .config import SETTINGS, model_full_name, model_backend, resolve_spec
from . import metrics as M


@dataclass
class LatencyPoint:
    reranker: str
    mode: str
    top_n: int
    n_queries: int
    p50_ms: float
    p95_ms: float
    p99_ms: float
    throughput_qps: float
    peak_vram_gb: float


def _synthetic(n_docs: int, q_chars: int = 60, d_chars: int = 400):
    q = "금융 상품의 중도해지 수수료는 어떻게 계산되나요?"[:q_chars]
    base = ("해당 약관에 따르면 중도 해지 시 적용되는 수수료와 이율은 다음과 같이 산정된다. ")
    doc = (base * ((d_chars // len(base)) + 1))[:d_chars]
    return q, [f"[{i}] {doc}" for i in range(n_docs)]


def _reset_vram():
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()
    except Exception:
        pass


def _peak_vram_gb() -> float:
    try:
        import torch
        if torch.cuda.is_available():
            return torch.cuda.max_memory_allocated() / (1024 ** 3)
    except Exception:
        pass
    return 0.0


def measure(reranker_key: str, mode: str, *, n_queries: int = 30, warmup: int = 2) -> list[dict]:
    import time
    from .rerankers import load_reranker

    _set_seed(SETTINGS.seed)  # 재현성(계획안 6절)
    reranker = load_reranker(reranker_key, mode)
    q, full_docs = _synthetic(max(SETTINGS.candidate_top_ns))
    try:
        # 워밍업
        for _ in range(warmup):
            reranker.score(q, full_docs[:SETTINGS.candidate_top_ns[0]])

        points = []
        for top_n in SETTINGS.candidate_top_ns:
            docs = full_docs[:top_n]
            _reset_vram()
            per_q = []
            for _ in range(n_queries):
                t0 = time.perf_counter()
                reranker.score(q, docs)
                per_q.append((time.perf_counter() - t0) * 1000.0)  # ms
            pct = M.percentiles(per_q)
            total_s = sum(per_q) / 1000.0
            points.append(asdict(LatencyPoint(
                reranker=reranker_key, mode=mode, top_n=top_n, n_queries=n_queries,
                p50_ms=round(pct["p50"], 2), p95_ms=round(pct["p95"], 2),
                p99_ms=round(pct["p99"], 2),
                throughput_qps=round(n_queries / total_s, 2) if total_s else 0.0,
                peak_vram_gb=round(_peak_vram_gb(), 3),
            )))
            print(f"[latency] {reranker_key}/{mode} top{top_n}: "
                  f"p95={pct['p95']:.1f}ms qps={points[-1]['throughput_qps']}")
        return points
    finally:
        _free(reranker)  # 예외에도 해제(measure_all 가 잡고 계속 → 누수 방지)


def measure_all(reranker_keys: list[str], modes: list[str]) -> list[dict]:
    out = []
    for rk in reranker_keys:
        for mode in modes:
            try:
                points = measure(rk, mode)
                out.extend(points)
                if _results.session_active():
                    _emit_latency_summary(rk, mode, points)
            except Exception as exc:
                print(f"[latency] {rk}/{mode} 실패: {exc}")
                out.append({"reranker": rk, "mode": mode, "error": str(exc)})
    return out


def _emit_latency_summary(reranker_key: str, mode: str, points: list[dict]) -> None:
    """latency 측정(여러 top_n) → model_test 규약 latency 스키마 summary.json (track='latency')."""
    model_full = model_full_name(reranker_key)
    backend, _ = model_backend(reranker_key)
    conditions = [{
        "condition": f"top{p['top_n']}", "top_n": p["top_n"], "n_queries": p["n_queries"],
        "p50_ms": p["p50_ms"], "p95_ms": p["p95_ms"], "p99_ms": p["p99_ms"],
        "throughput_qps": p["throughput_qps"], "peak_vram_gb": p["peak_vram_gb"],
    } for p in points]
    run_cfg = _results.build_run_config(
        benchmark="synthetic_rerank_latency", model_full_name=model_full,
        seed=SETTINGS.seed, precision=SETTINGS.precision,
        batch_size=SETTINGS.rerank_batch_size, max_seq_length=SETTINGS.max_doc_len,
        prompt_mode=mode, eval_script_path=str(__file__),
        extra={"backend": backend, "reranker_backend": resolve_spec(reranker_key).backend})
    payload = {
        "benchmark": f"synthetic_rerank_latency__{mode}", "model": model_full,
        "conditions": conditions, "prompt_mode": mode, "run_config": run_cfg,
    }
    _results.write_summary("latency", f"synthetic__{mode}", payload, model_full_name=model_full)


