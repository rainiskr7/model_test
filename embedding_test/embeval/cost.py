"""운영 비용 측정 — 계획안 4·5절. 품질 평가와 분리 측정한다.

두 조건 모두 측정(계획안 5절):
  ① 고정 batch latency  : 모든 모델 동일 batch(공정 비교)
  ② 최대 안정 batch throughput : 모델별 OOM 직전까지 batch 키워 실배포 처리량

부가 지표: 임베딩 차원, 피크 VRAM(GB), 벡터DB 비용 추정(문서수×dim×dtype).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, asdict

from evalcommon import free_model as _free
from evalcommon import results as _results

from .config import SETTINGS, model_backend, model_full_name


@dataclass
class CostResult:
    model_key: str
    prompt_mode: str
    embed_dim: int
    # ① 고정 batch
    fixed_batch: int
    fixed_latency_ms_per_batch: float
    fixed_throughput_docs_per_s: float
    # ② 최대 안정 batch
    max_stable_batch: int
    max_throughput_docs_per_s: float
    # 메모리
    peak_vram_gb: float
    # 벡터DB 비용 추정(예: 100만 문서)
    vectordb_gb_per_1m_docs: float


def _make_corpus(n: int, seq_chars: int = 400) -> list[str]:
    """결정적(고정) 한국어 풍 더미 코퍼스. 시드 영향 없는 합성 텍스트."""
    base = ("금융 시장 동향과 기업 실적 보고서를 요약한 문장입니다. "
            "검색 및 RAG 파이프라인의 인코딩 처리량을 측정하기 위한 텍스트. ")
    unit = (base * ((seq_chars // len(base)) + 1))[:seq_chars]
    return [f"[{i}] {unit}" for i in range(n)]


def _encode(model, texts: list[str], batch_size: int):
    return model.encode(texts, batch_size=batch_size, show_progress_bar=False)


def _reset_vram():
    import torch

    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()


def _peak_vram_gb() -> float:
    import torch

    if not torch.cuda.is_available():
        return 0.0
    return torch.cuda.max_memory_allocated() / (1024 ** 3)


def _dtype_bytes() -> int:
    return {"bf16": 2, "fp16": 2, "fp32": 4}[SETTINGS.precision]


def measure_model(model_key: str, prompt_mode: str, *,
                  warmup: int = 2, n_docs: int = 256,
                  max_batch_cap: int = 512) -> CostResult:
    import numpy as np

    from .models import load_model

    model = load_model(model_key, prompt_mode)
    corpus = _make_corpus(n_docs)
    try:
        # 워밍업(컴파일/캐시 안정화)
        for _ in range(warmup):
            _encode(model, corpus[: SETTINGS.fixed_batch_size], SETTINGS.fixed_batch_size)

        # 임베딩 차원
        sample = _encode(model, corpus[:2], 2)
        embed_dim = int(np.asarray(sample).shape[-1])

        # ① 고정 batch latency / throughput
        fb = SETTINGS.fixed_batch_size
        _reset_vram()
        n_batches = max(1, n_docs // fb)
        t0 = time.perf_counter()
        for b in range(n_batches):
            _encode(model, corpus[b * fb:(b + 1) * fb], fb)
        dt = time.perf_counter() - t0
        fixed_lat_ms = (dt / n_batches) * 1000.0
        fixed_tput = (n_batches * fb) / dt
        peak_fixed = _peak_vram_gb()

        # ② 최대 안정 batch (OOM 직전까지 2배씩 증가)
        max_stable, max_tput, peak_max = fb, fixed_tput, peak_fixed
        bs = fb * 2
        while bs <= max_batch_cap:
            try:
                _reset_vram()
                t0 = time.perf_counter()
                _encode(model, corpus[:bs] if bs <= n_docs else _make_corpus(bs), bs)
                dt = time.perf_counter() - t0
                max_stable, max_tput, peak_max = bs, bs / dt, _peak_vram_gb()
                bs *= 2
            except RuntimeError as exc:
                if "out of memory" in str(exc).lower():
                    print(f"[cost] {model_key} batch={bs} OOM → max_stable={max_stable}")
                    _reset_vram()
                    break
                raise

        peak = max(peak_fixed, peak_max)
        vdb_gb_1m = (1_000_000 * embed_dim * _dtype_bytes()) / (1024 ** 3)
        return CostResult(
            model_key=model_key, prompt_mode=prompt_mode, embed_dim=embed_dim,
            fixed_batch=fb, fixed_latency_ms_per_batch=round(fixed_lat_ms, 2),
            fixed_throughput_docs_per_s=round(fixed_tput, 2),
            max_stable_batch=max_stable, max_throughput_docs_per_s=round(max_tput, 2),
            peak_vram_gb=round(peak, 3), vectordb_gb_per_1m_docs=round(vdb_gb_1m, 3),
        )
    finally:
        _free(model)  # 예외 발생해도 모델 해제(measure_all 가 잡고 계속 → 누수 방지)


def measure_all(model_keys: list[str], prompt_modes: list[str]) -> list[dict]:
    out = []
    for mk in model_keys:
        for mode in prompt_modes:
            print(f"\n>>> [cost] model={mk} prompt={mode}")
            try:
                row = asdict(measure_model(mk, mode))
            except Exception as exc:
                print(f"[cost] {mk}/{mode} 실패: {exc}")
                row = {"model_key": mk, "prompt_mode": mode, "error": str(exc)}
            out.append(row)
            if _results.session_active():
                _emit_cost_summary(mk, mode, row)
    return out


def _emit_cost_summary(model_key: str, mode: str, row: dict) -> None:
    """cost 측정 1건 → model_test 규약 summary.json (track='cost')."""
    model_full = model_full_name(model_key)
    backend, _ = model_backend(model_key)
    has_err = "error" in row
    run_cfg = _results.build_run_config(
        benchmark="cost", model_full_name=model_full,
        seed=SETTINGS.seed, precision=SETTINGS.precision,
        batch_size=SETTINGS.fixed_batch_size, max_seq_length=SETTINGS.max_seq_length,
        prompt_mode=mode, extra={"backend": backend, "cost": row},
    )
    payload = {
        "benchmark": "cost", "model": model_full,
        "total": 0 if has_err else 1,
        "metric": "fixed_throughput_docs_per_s",
        "score": float(row.get("fixed_throughput_docs_per_s", 0.0)) if not has_err else 0.0,
        "prompt_mode": mode, "run_config": run_cfg,
    }
    if has_err:
        payload["error"] = row["error"]
    _results.write_summary("cost", f"cost__{model_key}__{mode}", payload,
                           model_full_name=model_full)
