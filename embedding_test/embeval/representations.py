"""repr 트랙 — dense/sparse/hybrid 표현 비교(멀티기능 BGE-M3, 로컬 FlagEmbedding 전용).

계획: MTEB dense 경로와 별개로, 동일 코퍼스/쿼리/qrels/캡/지표 위에서 세 표현을 직접 비교한다
(apples-to-apples, codex 검토 C). vLLM sparse 는 출력 포맷 미성숙이라 제외(로컬 한정).

점수:
  dense  : 정규화 dense 벡터 코사인(= 내적).
  sparse : lexical_weights 역색인으로 공유 토큰 가중합(= compute_lexical_matching_score 등가, 검토 A).
  hybrid : alpha*minmax_q(dense) + (1-alpha)*minmax_q(sparse), 쿼리별 min-max(검토 B).
           run_config.extra 에 hybrid_normalization='per_query_minmax' 로 명시.

결과: results/<safe_model>/<ts>/embedding/repr/<task>__<rep>/summary.json (metric=ndcg_at_10).
"""

from __future__ import annotations

from pathlib import Path

from evalcommon import free_model as _free, set_seed as _set_seed
from evalcommon import results as _results

from .config import (SETTINGS, REPR_TASKS, TaskSpec, model_full_name,
                     model_local_backend, model_representations, model_hybrid)
from . import metrics as M
from .retrieval_data import load_retrieval_data, relevance_aware_cap

_EVAL_KS = (1, 5, 10)
_PRIMARY_K = 10


def lexical_score(qw: dict, dw: dict) -> float:
    """공유 토큰 가중합. FlagEmbedding compute_lexical_matching_score 와 등가(검토 A)."""
    if len(qw) > len(dw):
        qw, dw = dw, qw
    return float(sum(w * dw[t] for t, w in qw.items() if t in dw))


def _effective_precision() -> str:
    """FlagEmbedding 은 use_fp16 만 받는다 → bf16 설정이어도 실제로는 fp16/fp32.

    summary 에 실제 실행 정밀도를 정직하게 기록하기 위함(codex 검토 #4: 보고/실제 불일치 방지).
    """
    return "fp16" if SETTINGS.precision in ("bf16", "fp16") else "fp32"


def _load_flag_model(hf_name: str, revision):
    from FlagEmbedding import BGEM3FlagModel
    use_fp16 = _effective_precision() == "fp16"
    # revision 지원 버전 차이 흡수
    try:
        return BGEM3FlagModel(hf_name, revision=revision, use_fp16=use_fp16)
    except TypeError:
        return BGEM3FlagModel(hf_name, use_fp16=use_fp16)


def _encode(model, texts: list[str], *, dense: bool, sparse: bool):
    out = model.encode(texts, batch_size=SETTINGS.fixed_batch_size,
                       max_length=SETTINGS.max_seq_length,
                       return_dense=dense, return_sparse=sparse,
                       return_colbert_vecs=False)
    return out


def _dense_scores(q_vec, doc_mat):
    import numpy as np
    return np.asarray(doc_mat) @ np.asarray(q_vec)  # 이미 정규화된 벡터 가정 → 코사인


def _build_sparse_index(doc_lws: list[dict]):
    """token_id -> list[(doc_idx, weight)] 역색인."""
    index: dict[str, list] = {}
    for di, lw in enumerate(doc_lws):
        for t, w in lw.items():
            index.setdefault(t, []).append((di, float(w)))
    return index


def _sparse_scores(q_lw: dict, index: dict, n_docs: int):
    import numpy as np
    scores = np.zeros(n_docs, dtype="float32")
    for t, wq in q_lw.items():
        posting = index.get(t)
        if not posting:
            continue
        wq = float(wq)
        for di, wd in posting:
            scores[di] += wq * wd
    return scores


def _minmax(x):
    import numpy as np
    x = np.asarray(x, dtype="float32")
    lo, hi = float(x.min()), float(x.max())
    if hi - lo < 1e-12:
        return np.zeros_like(x)
    return (x - lo) / (hi - lo)


def _rank(doc_ids: list[str], scores) -> list[str]:
    # 내림차순 + doc_id 결정적 tie-break
    order = sorted(range(len(doc_ids)), key=lambda i: (-float(scores[i]), doc_ids[i]))
    return [doc_ids[i] for i in order]


def _normalize_rows(mat):
    import numpy as np
    mat = np.asarray(mat, dtype="float32")
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    return mat / np.clip(norms, 1e-12, None)


def evaluate_task(model, spec: TaskSpec, model_key: str, representations: list[str],
                  *, overwrite: bool = False) -> list[dict]:
    import numpy as np

    data = load_retrieval_data(spec)
    corpus, queries, qrels, cap_info = relevance_aware_cap(data, SETTINGS.corpus_sample_size)
    if cap_info.get("capped"):
        print(f"[repr] {spec.name} 코퍼스 캡: {cap_info}")

    doc_ids = list(corpus)
    qids = list(queries)
    need_dense = any(r in ("dense", "hybrid") for r in representations)
    need_sparse = any(r in ("sparse", "hybrid") for r in representations)

    print(f"[repr] 인코딩 {spec.name}: docs={len(doc_ids)} queries={len(qids)} "
          f"(dense={need_dense} sparse={need_sparse})")
    doc_out = _encode(model, [corpus[d] for d in doc_ids], dense=need_dense, sparse=need_sparse)
    q_out = _encode(model, [queries[q] for q in qids], dense=need_dense, sparse=need_sparse)

    doc_dense = _normalize_rows(doc_out["dense_vecs"]) if need_dense else None
    q_dense = _normalize_rows(q_out["dense_vecs"]) if need_dense else None
    sparse_index = _build_sparse_index(doc_out["lexical_weights"]) if need_sparse else None

    alpha, hyb_norm = model_hybrid(model_key)
    # hybrid 정규화는 현재 per_query_minmax 만 구현 → 다른 값이 yaml 에 오면 summary 가 거짓이
    # 되므로 hard-fail(codex 검토 #5: 기록값과 실제 동작 불일치 방지).
    if "hybrid" in representations and hyb_norm != "per_query_minmax":
        raise SystemExit(
            f"[repr] hybrid_normalization='{hyb_norm}' 미구현 — 'per_query_minmax' 만 지원. "
            f"configs/models/{model_key}.yaml 수정 필요.")
    model_full = model_full_name(model_key)
    eff_prec = _effective_precision()
    out_recs = []

    for rep in representations:
        per_q = []
        for i, qid in enumerate(qids):
            rels = qrels.get(qid, {})
            d_sc = _dense_scores(q_dense[i], doc_dense) if need_dense else None
            s_sc = _sparse_scores(q_out["lexical_weights"][i], sparse_index, len(doc_ids)) \
                if need_sparse else None
            if rep == "dense":
                scores = d_sc
            elif rep == "sparse":
                scores = s_sc
            else:  # hybrid
                scores = alpha * _minmax(d_sc) + (1.0 - alpha) * _minmax(s_sc)
            ranking = _rank(doc_ids, scores)
            per_q.append(M.query_metrics(ranking, rels, _EVAL_KS))

        mean = M.mean_metrics(per_q)
        primary = mean.get(f"ndcg@{_PRIMARY_K}", 0.0)
        extra = {"representation": rep, "kind": "Retrieval", "backend": "flagembedding",
                 "configured_precision": SETTINGS.precision,  # FlagEmbedding 실제는 eff_prec
                 "corpus_cap": cap_info, "mean_metrics": {k: round(v, 6) for k, v in mean.items()}}
        if rep == "hybrid":
            extra["hybrid_alpha"] = alpha
            extra["hybrid_normalization"] = hyb_norm
        run_cfg = _results.build_run_config(
            benchmark=spec.name, model_full_name=model_full,
            seed=SETTINGS.seed, precision=eff_prec,  # 실제 실행 정밀도(fp16) 기록
            batch_size=SETTINGS.fixed_batch_size, max_seq_length=SETTINGS.max_seq_length,
            prompt_mode=None, dataset_id=None,
            eval_script_path=str(Path(__file__).resolve()), extra=extra)
        payload = {
            "benchmark": spec.name, "model": model_full, "total": len(per_q),
            "metric": "ndcg_at_10", "score": round(float(primary), 6),
            "representation": rep, "kind": "Retrieval", "run_config": run_cfg,
        }
        if _results.session_active():
            _results.write_summary("repr", f"{spec.name}__{rep}", payload,
                                   model_full_name=model_full)
        print(f"[repr] {spec.name}/{rep}: ndcg@10={primary:.4f} (queries={len(per_q)})")
        out_recs.append(payload)
    return out_recs


def run_repr(model_keys: list[str], task_specs: list[TaskSpec] | None = None,
             representations: list[str] | None = None, *, overwrite: bool = False) -> None:
    """repr 트랙 실행. 표현은 yaml(model_representations)로 결정, 인자로 좁힐 수 있음."""
    _set_seed(SETTINGS.seed)
    specs = task_specs or REPR_TASKS
    retr = [s for s in specs if s.kind == "Retrieval"]
    if not _results.session_active():
        print("[repr] ⚠️ 활성 세션 없음 → summary.json 미기록(stdout 결과만). "
              "./start_eval_session.sh 후 실행 권장.")

    failures: list[str] = []
    produced = 0
    for mk in model_keys:
        if model_local_backend(mk) != "flagembedding":
            raise SystemExit(
                f"[repr] '{mk}' 는 flagembedding backend 가 아님(sparse/hybrid 불가). "
                f"configs/models/{mk}.yaml 의 local_backend: flagembedding + representations 확인. "
                f"sparse 가능 모델은 BAAI/bge-m3(원본)뿐 — 한국어 파인튜닝은 dense 전용.")
        reps = representations or model_representations(mk)
        from .config import resolve_spec
        spec = resolve_spec(mk)
        print(f"\n>>> [repr] model={mk} ({spec.hf_name}) representations={reps}")
        model = _load_flag_model(spec.hf_name, spec.revision)
        try:
            for s in retr:
                try:
                    recs = evaluate_task(model, s, mk, reps, overwrite=overwrite)
                    produced += len(recs)
                except SystemExit:
                    raise  # 설정 오류(미구현 normalization 등)는 즉시 중단
                except Exception as exc:
                    failures.append(f"{mk}/{s.name}: {exc}")
                    print(f"[repr] {s.name} 실패: {exc}")
        finally:
            _free(model)

    # 트랙 본체는 fail-fast(CONVENTIONS §6): 설정된 태스크가 하나라도 실패하거나
    # 결과가 0건이면 비정상 종료 → run_full_eval 이 'repr 성공'으로 오인하지 않게 함(검토 #1).
    if failures:
        raise SystemExit(f"[repr] 실패한 태스크 {len(failures)}건: {failures}")
    if produced == 0:
        raise SystemExit("[repr] 생성된 결과 0건 — 태스크/데이터/세션 확인.")
