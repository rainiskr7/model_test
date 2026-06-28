"""1차 검색 후보(top-N) 생성 + 디스크 캐시 — 계획안 3-2(retrieval→rerank 변환).

retrieval 태스크를 reranking 으로 평가하려면 '동결된(frozen) 1차 후보 집합'이 필요하다.
임베딩 모델로 쿼리당 top-N 문서를 뽑아 **캐시**한다. 캐시 키 = (task, embedder, top_n).

캐시가 있으면 재사용 → 임베딩 인코딩(가장 비싼 단계)을 건너뛰고 rerank 만 다시 돌릴 수 있다.
= '언제든 데이터셋별 재시작'의 핵심(계획안 6절).

candidate 형식: {qid: [(doc_id, first_stage_score), ...]}  (점수 내림차순)
"""

from __future__ import annotations

import json
from pathlib import Path

from .config import SETTINGS, TaskSpec


def cache_path(spec: TaskSpec, embedder_key: str, top_n: int) -> Path:
    safe = spec.name.replace("/", "_")
    sub = f"_{spec.subset}" if spec.subset else ""
    return Path(SETTINGS.cache_dir) / f"{safe}{sub}__{embedder_key}__top{top_n}.json"


def load_cached(spec: TaskSpec, embedder_key: str, top_n: int) -> dict | None:
    p = cache_path(spec, embedder_key, top_n)
    if not p.exists():
        return None
    try:
        raw = json.loads(p.read_text())
        # JSON 은 튜플을 리스트로 저장 → [doc_id, score] 복원
        return {qid: [(d, float(s)) for d, s in cand] for qid, cand in raw.items()}
    except Exception as exc:
        print(f"[firststage] 캐시 손상 무시({p}): {exc}")
        return None


def build_candidates(spec: TaskSpec, data: dict, embedder_key: str, top_n: int,
                     *, overwrite: bool = False) -> dict:
    """임베딩 1차 검색으로 쿼리당 top_n 후보 생성(+캐시). 캐시 있으면 재사용."""
    if not overwrite:
        cached = load_cached(spec, embedder_key, top_n)
        if cached is not None:
            print(f"[firststage] 캐시 사용: {spec.name}/{embedder_key}/top{top_n} "
                  f"({len(cached)} queries)")
            return cached

    import numpy as np
    from evalcommon import free_model
    from .embedders import load_embedder

    corpus, queries = data["corpus"], data["queries"]
    doc_ids = list(corpus)
    doc_texts = [corpus[d] for d in doc_ids]
    if SETTINGS.corpus_limit:
        doc_ids = doc_ids[: SETTINGS.corpus_limit]
        doc_texts = doc_texts[: SETTINGS.corpus_limit]

    print(f"[firststage] 인코딩 {spec.name}/{embedder_key}: "
          f"docs={len(doc_ids)} queries={len(queries)}")
    model = load_embedder(embedder_key)
    try:
        doc_emb = model.encode(doc_texts, batch_size=64, normalize_embeddings=True,
                               show_progress_bar=True, convert_to_numpy=True)
        qids = list(queries)
        q_emb = model.encode([queries[q] for q in qids], batch_size=64,
                             normalize_embeddings=True, show_progress_bar=True,
                             convert_to_numpy=True)
    finally:
        # 1차 임베더는 인코딩 후 곧바로 해제(리랭커 로드 전 VRAM 확보).
        free_model(model)

    doc_emb = np.asarray(doc_emb)
    q_emb = np.asarray(q_emb)
    candidates: dict[str, list] = {}
    n = min(top_n, len(doc_ids))
    for i, qid in enumerate(qids):
        sims = doc_emb @ q_emb[i]
        # 부분 정렬로 top-n
        idx = np.argpartition(-sims, n - 1)[:n] if n < len(sims) else np.arange(len(sims))
        idx = idx[np.argsort(-sims[idx])]
        candidates[qid] = [(doc_ids[j], float(sims[j])) for j in idx]

    _save(spec, embedder_key, top_n, candidates)
    return candidates


def _save(spec: TaskSpec, embedder_key: str, top_n: int, candidates: dict) -> None:
    p = cache_path(spec, embedder_key, top_n)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(candidates, ensure_ascii=False))
    print(f"[firststage] 캐시 저장 → {p}")
