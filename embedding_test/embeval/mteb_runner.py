"""MTEB 평가 실행 — 스모크/한국어/금융 공통 코어.

계획안 5절 절차 1·3·4 를 담당. 모델 × prompt_mode × 태스크 매트릭스로 실행하고
mteb 가 results_dir 에 점수 JSON 을 남긴다(aggregate 단계에서 표로 정리).
"""

from __future__ import annotations

from pathlib import Path

from evalcommon import (get_task as _get_task, free_model as _free,
                        set_seed as _set_seed)
from evalcommon import results as _results

from .config import SETTINGS, TaskSpec, model_backend, model_full_name
from .models import load_model


def _resolve_tasks(specs: list[TaskSpec], include_fallback: bool):
    """TaskSpec 목록 → mteb 태스크 객체. fallback 은 기본 제외."""
    names = [s.name for s in specs if include_fallback or s.status != "fallback"]
    # 중복 제거(순서 유지)
    seen: set[str] = set()
    ordered = [n for n in names if not (n in seen or seen.add(n))]
    tasks = []
    missing = []
    for n in ordered:
        try:
            tasks.append(_get_task(n))
        except Exception as exc:
            missing.append((n, str(exc)))
    if missing:
        print("[runner] ⚠️ registry 에서 못 찾은 태스크(건너뜀):")
        for n, e in missing:
            print(f"         - {n}: {e}")
    return tasks


def _build_encode_kwargs() -> dict:
    # encode_kwargs 는 model.encode() 로 전달된다 → batch_size 만 안전하게 둔다.
    # (코덱스 리뷰: corpus_chunk_size 는 encode kwarg 가 아니라 retrieval 평가기 옵션.
    #  여기에 넣으면 .encode() 로 새어 들어가 실패/무시될 수 있어 제거함.)
    return {"batch_size": SETTINGS.fixed_batch_size}


def run_tasks(
    group_name: str,
    tasks: list,  # mteb 태스크 객체 목록
    model_keys: list[str],
    prompt_modes: list[str],
    *,
    overwrite: bool = False,
) -> Path:
    """이미 해결된 mteb 태스크 객체 목록을 모델 × prompt_mode 로 평가.

    여러 태스크를 한 번의 mteb.MTEB(tasks=...) 호출로 '묶어' 실행한다(MTEB 네이티브 번들).
    출력: results/<group_name>/<model__mode>/...

    재시작/재개(요구사항): overwrite=False(기본) 이면 mteb 가 이미 결과 JSON 이 있는
    (모델×모드×태스크) 조합을 자동으로 건너뛴다. 따라서 중간에 끊겨도 같은 명령을
    다시 실행하면 '데이터셋 단위'로 남은 것만 이어서 돈다. 특정 데이터셋만 강제
    재실행하려면 overwrite=True (CLI --overwrite) 로 그 태스크만 지정해 호출한다.
    """
    import mteb

    _set_seed(SETTINGS.seed)
    if not tasks:
        raise RuntimeError(f"[{group_name}] 실행 가능한 태스크가 없음. verify 로 태스크명 확정 필요.")

    base = Path(SETTINGS.results_dir) / group_name
    encode_kwargs = _build_encode_kwargs()
    for model_key in model_keys:
        for mode in prompt_modes:
            out = base / f"{model_key}__{mode}"
            out.mkdir(parents=True, exist_ok=True)
            print(f"\n>>> [{group_name}] model={model_key} prompt={mode} "
                  f"tasks={[t.metadata.name for t in tasks]} "
                  f"(overwrite={overwrite}; False면 완료분 자동 건너뜀=재개)")
            model = load_model(model_key, mode)
            try:
                mteb.MTEB(tasks=tasks).run(
                    model, output_folder=str(out), encode_kwargs=encode_kwargs,
                    overwrite_results=overwrite, verbosity=1,
                )
                # model_test 규약 출력(세션 활성 시에만). 기존 mteb 네이티브 출력은 그대로 둠.
                if _results.session_active():
                    _emit_summaries(out, group_name, model_key, mode)
            finally:
                _free(model)  # run() 이 실패해도 해제(누수 방지)
    print(f"\n[{group_name}] 완료 → {base}")
    return base


def _count_mains(scores: dict) -> int:
    """scores 안의 main_score 항목 수.

    ⚠️ 이는 '평가 샘플 수'가 아니라 '점수 항목(split×subset) 수'다. mteb 결과 JSON 에서
    샘플 수를 일관되게 얻기 어려워, summary.total 에는 이 값을 넣되 의미는 score_entries 다
    (payload 에 total_kind='score_entries' 로 명시). sanity 의 total==0 게이트(=결과 없음)
    목적에는 충분하다.
    """
    c = 0
    for v in (scores or {}).values():
        entries = v if isinstance(v, list) else [v]
        c += sum(1 for e in entries if isinstance(e, dict) and "main_score" in e)
    return c


def _emit_summaries(out: Path, track: str, model_key: str, mode: str) -> None:
    """방금 mteb 가 out 에 남긴 태스크 JSON → model_test 규약 summary.json 으로 변환.

    점수/지표 추출은 aggregate 와 동일 로직(test-split 우선, 다중 subset 평균)을 재사용한다.
    """
    import json
    from .aggregate import _extract_score, PRIMARY_METRIC, TASK_KIND

    model_full = model_full_name(model_key)
    backend, endpoint_cfg = model_backend(model_key)
    base_url = endpoint_cfg.get("base_url") if backend == "endpoint" else None

    for jf in out.rglob("*.json"):
        if jf.name == "model_meta.json":
            continue
        try:
            payload = json.loads(jf.read_text())
        except Exception:
            continue
        got = _extract_score(payload)
        if got is None:
            continue
        task_name, score = got
        kind = TASK_KIND.get(task_name, "?")
        metric = PRIMARY_METRIC.get(kind, "main_score")
        total = max(1, _count_mains(payload.get("scores", {})))
        run_cfg = _results.build_run_config(
            benchmark=task_name, model_full_name=model_full, base_url=base_url,
            seed=SETTINGS.seed, precision=SETTINGS.precision,
            batch_size=SETTINGS.fixed_batch_size, max_seq_length=SETTINGS.max_seq_length,
            prompt_mode=mode, eval_script_path=str(Path(__file__).resolve()),
            extra={"kind": kind, "backend": backend},
        )
        payload_out = {
            "benchmark": task_name, "model": model_full, "total": total,
            "total_kind": "score_entries",  # total 은 샘플수가 아니라 점수항목 수(_count_mains 참고)
            "metric": metric, "score": round(float(score), 6),
            "prompt_mode": mode, "kind": kind, "run_config": run_cfg,
        }
        _results.write_summary(track, f"{task_name}__{mode}", payload_out,
                               model_full_name=model_full)


def run_group(
    group_name: str,
    task_specs: list[TaskSpec],
    model_keys: list[str],
    prompt_modes: list[str],
    *,
    include_fallback: bool = False,
    overwrite: bool = False,
) -> Path:
    """한 태스크 그룹(TaskSpec 목록)을 평가. 내부적으로 run_tasks 로 번들 실행."""
    tasks = _resolve_tasks(task_specs, include_fallback)
    return run_tasks(group_name, tasks, model_keys, prompt_modes, overwrite=overwrite)


def run_single_task(
    task_name: str,
    model_keys: list[str],
    prompt_modes: list[str],
    *,
    group_name: str = "single",
    overwrite: bool = False,
) -> Path:
    """태스크 1개만 평가(테스트 단위 실행/재시작). 계획안 디버깅/부분 재실행용."""
    tasks = _resolve_tasks([TaskSpec(task_name, kind="?")], include_fallback=True)
    if not tasks:
        raise RuntimeError(f"태스크 '{task_name}' 를 registry 에서 찾지 못함. verify 로 정식명 확인.")
    return run_tasks(group_name, tasks, model_keys, prompt_modes, overwrite=overwrite)
