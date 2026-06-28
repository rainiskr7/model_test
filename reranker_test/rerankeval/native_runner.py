"""MTEB native reranking 태스크 실행 — 계획안 3-2(MIRACLReranking 등).

native reranking 태스크는 후보가 데이터셋에 내장돼 있어 1차 검색이 불필요하다.
mteb 의 reranking 평가 루프에 cross-encoder/리랭커를 넣어 그대로 묶어 실행한다.

스모크(AskUbuntuDupQuestions/SciDocsRR)도 native reranking 이라 여기서 처리.
재시작: overwrite=False(기본) 이면 완료 태스크는 mteb 가 건너뛴다.

⚠️ 실행 전 검증 필요(계획안 8절, codex 검토 #4·#6):
  - 고정 버전 mteb==1.38.30 에서 reranking 태스크가 CrossEncoder 를 직접 받는지 확인.
    만약 임베딩 기반 RerankingEvaluator 만 지원하면, native 경로 대신 데이터셋의 내장 후보를
    꺼내 우리 metrics 로 평가하는 수동 evaluator 로 대체해야 한다.
  - MIRACLReranking 의 한국어 subset(=spec.subset 'ko') 이 실제로 선택되는지 확인.
    아래 _resolve 는 subset 을 강제하지 않으므로, 필요 시 언어/subset 필터를 추가한다.
"""

from __future__ import annotations

from pathlib import Path

from evalcommon import get_task as _get_task, free_model as _free, set_seed as _set_seed
from evalcommon import results as _results

from .config import SETTINGS, TaskSpec, model_full_name, model_backend, all_task_specs


def _resolve(task_specs: list[TaskSpec]):
    tasks, missing = [], []
    for s in task_specs:
        if s.kind != "reranking":
            continue
        try:
            tasks.append(_get_task(s.name))
        except Exception as exc:
            missing.append((s.name, str(exc)))
    if missing:
        print("[native] registry 미발견(건너뜀):")
        for n, e in missing:
            print(f"         - {n}: {e}")
    return tasks


def run_reranking_tasks(task_specs: list[TaskSpec], reranker_keys: list[str],
                        modes: list[str], *, group: str = "native",
                        overwrite: bool = False) -> Path:
    """native reranking 태스크를 리랭커 × mode 로 묶어 실행."""
    import mteb
    from .rerankers import load_reranker

    _set_seed(SETTINGS.seed)  # 재현성(계획안 6절)
    tasks = _resolve(task_specs)
    base = Path(SETTINGS.results_dir) / group
    if not tasks:
        print(f"[native] 실행할 reranking 태스크 없음(group={group}).")
        return base

    for rk in reranker_keys:
        for mode in modes:
            out = base / f"{rk}__{mode}"
            out.mkdir(parents=True, exist_ok=True)
            print(f"\n>>> [native:{group}] reranker={rk} mode={mode} "
                  f"tasks={[t.metadata.name for t in tasks]}")
            # 비호환 스코어링 백엔드(예: causal_lm)가 전체 native 런을 죽이지 않도록
            # (reranker, mode) 단위로 격리. 실패는 기록하고 다음 모델로 진행.
            reranker = None
            try:
                reranker = load_reranker(rk, mode)
                model = _mteb_compatible(reranker)  # CrossEncoder 만 native 호환
            except Exception as exc:
                print(f"[native] 건너뜀 {rk}/{mode}: {exc}")
                (out / "_skipped.txt").write_text(str(exc))
                if reranker is not None:
                    _free(reranker)  # 로드됐는데 호환 변환 실패 시 해제(누수 방지)
                continue
            try:
                # mteb 는 reranking 태스크에서 모델의 predict/score 를 사용한다.
                mteb.MTEB(tasks=tasks).run(
                    model, output_folder=str(out),
                    overwrite_results=overwrite, verbosity=1,
                )
                if _results.session_active():
                    _emit_native_summaries(out, group, rk, mode)
            finally:
                _free(reranker)  # run() 이 실패해도 해제(누수 방지)
    print(f"\n[native:{group}] 완료 → {base}")
    return base


def _extract_main_score(payload: dict):
    """mteb 결과 JSON → (task_name, main_score, n_entries). embedding 과 동일 규칙."""
    name = payload.get("task_name") or payload.get("mteb_dataset_name")
    scores = payload.get("scores")
    if name is None or not isinstance(scores, dict):
        return None
    keys = list(scores.keys())
    ordered = ([k for k in ("test", "dev", "validation") if k in keys]
               + sorted(k for k in keys if k not in ("test", "dev", "validation")))
    for split in ordered:
        v = scores[split]
        entries = v if isinstance(v, list) else [v]
        mains = [e["main_score"] for e in entries if isinstance(e, dict) and "main_score" in e]
        if mains:
            return name, float(sum(mains) / len(mains)), len(mains)
    if "main_score" in scores:
        return name, float(scores["main_score"]), 1
    return None


def _emit_native_summaries(out, group: str, rk: str, mode: str) -> None:
    """native(mteb) 결과 → model_test 규약 summary.json (track='native')."""
    import json
    specs = {s.name: s for s in all_task_specs()}
    model_full = model_full_name(rk)
    backend, _ = model_backend(rk)
    for jf in out.rglob("*.json"):
        if jf.name in ("model_meta.json", "_skipped.txt"):
            continue
        try:
            payload = json.loads(jf.read_text())
        except Exception:
            continue
        got = _extract_main_score(payload)
        if got is None:
            continue
        task_name, score, n = got
        spec = specs.get(task_name)
        metric = (f"{spec.primary_metric}@{spec.primary_k}"
                  if spec and spec.primary_metric in ("ndcg", "precision") else "main_score")
        run_cfg = _results.build_run_config(
            benchmark=task_name, model_full_name=model_full,
            seed=SETTINGS.seed, precision=SETTINGS.precision,
            batch_size=SETTINGS.rerank_batch_size, max_seq_length=SETTINGS.max_doc_len,
            prompt_mode=mode, eval_script_path=str(Path(__file__).resolve()),
            extra={"kind": "reranking", "backend": backend, "group": group})
        payload_out = {
            "benchmark": task_name, "model": model_full, "total": max(1, n),
            "total_kind": "score_entries", "metric": metric, "score": round(score, 6),
            "prompt_mode": mode, "kind": "reranking", "run_config": run_cfg,
        }
        _results.write_summary("native", f"{task_name}__{mode}", payload_out,
                               model_full_name=model_full)


def _mteb_compatible(reranker):
    """mteb reranking 평가가 기대하는 인터페이스로 어댑트.

    CrossEncoder 백엔드는 내부 .model(SentenceTransformer CrossEncoder)을 그대로 노출.
    causal_lm 등은 mteb 가 요구하는 predict 시그니처를 충족하는 래퍼가 필요 → 실행 전 확인.
    """
    inner = getattr(reranker, "model", None)
    # sentence_transformers CrossEncoder 는 mteb cross-encoder 평가와 직접 호환
    if inner is not None and inner.__class__.__name__ == "CrossEncoder":
        return inner
    # 그 외(causal_lm 등): mteb 호환 predict 래퍼 제공 필요(미설치 환경이라 보류)
    raise NotImplementedError(
        "native reranking 에 CrossEncoder 외 백엔드를 쓰려면 mteb 호환 predict 래퍼가 필요합니다. "
        "causal_lm 백엔드는 retrieval 경로(2-stage rerank_runner)로 평가하거나 래퍼를 구현하세요.")


