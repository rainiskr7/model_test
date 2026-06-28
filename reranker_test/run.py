#!/usr/bin/env python3
"""rerankeval CLI — 기능별/테스트별 실행 진입점 (계획안 6절 절차).

예시:
  python run.py env                          # 환경/버전 기록
  python run.py verify                       # ① 데이터셋 실재성/성격 검증(게이트)
  python run.py smoke                         # ① 스모크(native reranking)
  python run.py native --tasks MIRACLReranking   # native reranking 평가
  python run.py rerank                        # ② retrieval 4종 2-stage A/B
  python run.py task Ko-StrategyQA            # 테스트 단위(단일 데이터셋)
  python run.py latency                       # ③ latency/효율(candidate 민감도)
  python run.py aggregate                     # 결과 매트릭스 정리

공통 옵션:
  --rerankers bge-reranker-v2-m3 ko-reranker ...   (기본: config 전체)
  --modes recommended controlled
  --embedder bge-m3-ko                              (1차 검색 임베딩, 실행 인자)
  --overwrite                                       (완료분도 강제 재실행; 기본은 재개)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rerankeval.config import (RERANKERS, PROMPT_MODES, FIRST_STAGE_EMBEDDERS,
                               DEFAULT_EMBEDDER, SETTINGS, KOREAN_TASKS, SMOKE_TASKS,
                               all_task_specs)


def _common(p):
    p.add_argument("--rerankers", nargs="+", default=list(RERANKERS), choices=list(RERANKERS),
                   help="리랭커 키(configs/models/*.yaml 발견)")
    p.add_argument("--modes", nargs="+", default=list(PROMPT_MODES), choices=list(PROMPT_MODES))
    p.add_argument("--embedder", default=DEFAULT_EMBEDDER, choices=list(FIRST_STAGE_EMBEDDERS),
                   help="1차 검색 임베딩(retrieval 태스크용)")
    p.add_argument("--overwrite", action="store_true", help="완료분 강제 재실행(기본: 재개)")


def cmd_env(_):
    import platform
    info = {"python": platform.python_version()}
    for mod in ("torch", "mteb", "sentence_transformers", "transformers", "numpy"):
        try:
            info[mod] = __import__(mod).__version__
        except Exception as e:
            info[mod] = f"MISSING ({e})"
    try:
        import torch
        info["cuda"] = torch.cuda.is_available()
        if torch.cuda.is_available():
            info["gpu"] = torch.cuda.get_device_name(0)
    except Exception:
        pass
    print(json.dumps(info, indent=2, ensure_ascii=False))


def cmd_verify(_):
    from rerankeval.datasets import verify_all, print_report
    raise SystemExit(0 if print_report(verify_all()) else 1)


def cmd_smoke(args):
    from rerankeval.native_runner import run_reranking_tasks
    run_reranking_tasks(SMOKE_TASKS, args.rerankers, args.modes,
                        group="smoke", overwrite=args.overwrite)


def cmd_native(args):
    from rerankeval.native_runner import run_reranking_tasks
    specs = _filter_tasks(KOREAN_TASKS, args.tasks, kind="reranking")
    run_reranking_tasks(specs, args.rerankers, args.modes,
                        group="native", overwrite=args.overwrite)


def cmd_rerank(args):
    from rerankeval.rerank_runner import run_retrieval_tasks
    specs = _filter_tasks(KOREAN_TASKS, args.tasks, kind="retrieval")
    run_retrieval_tasks(specs, args.rerankers, args.embedder, args.modes,
                        overwrite=args.overwrite)


def cmd_task(args):
    """단일 데이터셋만 평가(테스트 단위). kind 에 따라 native/2-stage 자동 분기."""
    spec = next((s for s in all_task_specs() if s.name == args.task_name), None)
    if spec is None:
        raise SystemExit(f"알 수 없는 태스크: {args.task_name}")
    if spec.kind == "reranking":
        from rerankeval.native_runner import run_reranking_tasks
        run_reranking_tasks([spec], args.rerankers, args.modes,
                            group="single", overwrite=args.overwrite)
    else:
        from rerankeval.rerank_runner import run_retrieval_tasks
        run_retrieval_tasks([spec], args.rerankers, args.embedder, args.modes,
                            overwrite=args.overwrite)


def cmd_latency(args):
    from rerankeval.latency import measure_all
    rows = measure_all(args.rerankers, args.modes)
    out = Path(SETTINGS.results_dir) / "latency.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=2, ensure_ascii=False))
    print(f"\n[latency] → {out}")


def cmd_aggregate(_):
    from rerankeval.aggregate import write_reports
    lat = Path(SETTINGS.results_dir) / "latency.json"
    write_reports(latency_json=lat if lat.exists() else None)


def _filter_tasks(specs, names, *, kind):
    pool = [s for s in specs if s.kind == kind]
    if names:
        valid = {s.name for s in pool}
        unknown = [n for n in names if n not in valid]
        if unknown:
            raise SystemExit(
                f"알 수 없는 {kind} 태스크: {unknown}. 가능: {sorted(valid)}")
        pool = [s for s in pool if s.name in names]
    return pool


def build_parser():
    p = argparse.ArgumentParser(description="rerankeval — 한국어 리랭커 비교 평가")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("env").set_defaults(func=cmd_env)
    sub.add_parser("verify").set_defaults(func=cmd_verify)

    ps = sub.add_parser("smoke"); _common(ps); ps.set_defaults(func=cmd_smoke)

    pn = sub.add_parser("native"); _common(pn)
    pn.add_argument("--tasks", nargs="*", help="특정 태스크명만")
    pn.set_defaults(func=cmd_native)

    pr = sub.add_parser("rerank"); _common(pr)
    pr.add_argument("--tasks", nargs="*", help="특정 태스크명만")
    pr.set_defaults(func=cmd_rerank)

    pt = sub.add_parser("task"); pt.add_argument("task_name"); _common(pt)
    pt.set_defaults(func=cmd_task)

    pl = sub.add_parser("latency"); _common(pl); pl.set_defaults(func=cmd_latency)
    sub.add_parser("aggregate").set_defaults(func=cmd_aggregate)
    return p


def main():
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
