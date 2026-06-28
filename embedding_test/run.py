#!/usr/bin/env python3
"""embeval CLI — 기능별/테스트별 실행 진입점.

계획안 5절 절차를 서브커맨드로 노출한다. 각 단계를 독립적으로 실행 가능하다.

예시:
  python run.py env                       # 환경/버전 기록(재현성)
  python run.py verify [--load]           # ① 데이터셋 실재성 검증(게이트)
  python run.py list-ko                   # registry 한국어 태스크 실재명 덤프
  python run.py list-benchmarks           # MTEB 공식 벤치마크 목록
  python run.py smoke                     # ① 스모크(파이프라인 검증)
  python run.py korean                    # ③ 범용 한국어
  python run.py financial                 # ④ 금융 트랙 1
  python run.py task KLUE-STS             # 테스트 단위(단일 태스크)만 실행
  python run.py bundle korean             # MTEB 번들로 한국어 묶어 실행
  python run.py official "MTEB(kor, v1)"  # MTEB 공식 벤치마크 실행
  python run.py cost                      # ⑤ 운영 비용 측정
  python run.py aggregate                 # ⑥ 결과 매트릭스 정리

공통 옵션:
  --models qwen3-8b kanana-2.1b bge-m3-ko   (기본: 전체)
  --modes recommended controlled            (기본: 전체)
  --include-fallback                        (대체 태스크 포함)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from embeval.config import MODELS, PROMPT_MODES, SETTINGS, models_with_track


def _common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--models", nargs="+", default=list(MODELS),
                   choices=list(MODELS), help="평가할 모델 키")
    p.add_argument("--modes", nargs="+", default=list(PROMPT_MODES),
                   choices=list(PROMPT_MODES), help="prompt 모드")
    p.add_argument("--include-fallback", action="store_true",
                   help="대체(fallback) 태스크 포함")
    p.add_argument("--overwrite", action="store_true",
                   help="이미 완료된 데이터셋도 강제 재실행(기본: 완료분은 건너뛰고 재개)")


def cmd_env(_):
    import platform
    info = {"python": platform.python_version()}
    for mod in ("torch", "mteb", "sentence_transformers", "transformers", "numpy"):
        try:
            m = __import__(mod)
            info[mod] = getattr(m, "__version__", "?")
        except Exception as e:
            info[mod] = f"MISSING ({e})"
    try:
        import torch
        info["cuda_available"] = torch.cuda.is_available()
        if torch.cuda.is_available():
            info["gpu"] = torch.cuda.get_device_name(0)
            info["cuda"] = torch.version.cuda
    except Exception:
        pass
    print(json.dumps(info, indent=2, ensure_ascii=False))


def cmd_verify(args):
    from embeval.datasets import verify_all, print_report
    ok = print_report(verify_all(load=args.load))
    raise SystemExit(0 if ok else 1)


def cmd_list_ko(_):
    from embeval.datasets import list_korean_tasks
    names = list_korean_tasks()
    print(f"\n=== MTEB registry 한국어 태스크 ({len(names)}개) ===")
    for n in names:
        print(" -", n)


def cmd_list_benchmarks(_):
    from embeval.benchmarks import list_official_benchmarks
    for n in list_official_benchmarks():
        print(" -", n)


def _run_group(group, args):
    from embeval import config
    from embeval.mteb_runner import run_group
    specs = {"smoke": config.SMOKE_TASKS, "korean": config.KOREAN_TASKS,
             "financial": config.FINANCIAL_TASKS}[group]
    run_group(group, specs, args.models, args.modes,
              include_fallback=args.include_fallback, overwrite=args.overwrite)


def cmd_smoke(args):
    _run_group("smoke", args)


def cmd_korean(args):
    _run_group("korean", args)


def cmd_financial(args):
    _run_group("financial", args)


def cmd_task(args):
    from embeval.mteb_runner import run_single_task
    run_single_task(args.task_name, args.models, args.modes, overwrite=args.overwrite)


def cmd_bundle(args):
    from embeval.benchmarks import run_named_bundle
    run_named_bundle(args.bundle_name, args.models, args.modes,
                     include_fallback=args.include_fallback, overwrite=args.overwrite)


def cmd_official(args):
    from embeval.benchmarks import run_official_benchmark
    run_official_benchmark(args.benchmark_name, args.models, args.modes,
                           overwrite=args.overwrite)


def cmd_repr(args):
    """dense/sparse/hybrid 표현 비교(멀티기능 BGE-M3, 로컬 FlagEmbedding 전용)."""
    from embeval.representations import run_repr
    run_repr(args.models, representations=args.representations, overwrite=args.overwrite)


def cmd_cost(args):
    from embeval.cost import measure_all
    rows = measure_all(args.models, args.modes)
    out = Path(SETTINGS.results_dir) / "cost.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=2, ensure_ascii=False))
    print(f"\n[cost] → {out}")


def cmd_aggregate(args):
    from embeval.aggregate import write_reports
    cost = Path(SETTINGS.results_dir) / "cost.json"
    write_reports(cost_json=cost if cost.exists() else None)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="embeval — 임베딩 모델 비교 평가 하니스")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("env", help="환경/버전 기록").set_defaults(func=cmd_env)

    pv = sub.add_parser("verify", help="데이터셋 실재성 검증(게이트)")
    pv.add_argument("--load", action="store_true", help="실제 데이터 로드까지 시도")
    pv.set_defaults(func=cmd_verify)

    sub.add_parser("list-ko", help="registry 한국어 태스크 목록").set_defaults(func=cmd_list_ko)
    sub.add_parser("list-benchmarks", help="MTEB 공식 벤치마크 목록").set_defaults(func=cmd_list_benchmarks)

    for name, fn in [("smoke", cmd_smoke), ("korean", cmd_korean), ("financial", cmd_financial)]:
        sp = sub.add_parser(name, help=f"{name} 그룹 평가")
        _common(sp)
        sp.set_defaults(func=fn)

    pt = sub.add_parser("task", help="단일 태스크만 평가(테스트 단위)")
    pt.add_argument("task_name")
    _common(pt)
    pt.set_defaults(func=cmd_task)

    pb = sub.add_parser("bundle", help="MTEB 번들로 그룹 묶어 실행")
    pb.add_argument("bundle_name", choices=["smoke", "korean", "financial"])
    _common(pb)
    pb.set_defaults(func=cmd_bundle)

    po = sub.add_parser("official", help="MTEB 공식 벤치마크 실행")
    po.add_argument("benchmark_name")
    _common(po)
    po.set_defaults(func=cmd_official)

    pr = sub.add_parser("repr", help="dense/sparse/hybrid 표현 비교(FlagEmbedding)")
    pr.add_argument("--models", nargs="+", default=models_with_track("repr"), choices=list(MODELS),
                    help="평가할 모델 키(yaml tracks 에 repr 포함, flagembedding backend 필요)")
    pr.add_argument("--representations", nargs="+", default=None,
                    choices=["dense", "sparse", "hybrid"],
                    help="기본: yaml representations")
    pr.add_argument("--overwrite", action="store_true")
    pr.set_defaults(func=cmd_repr)

    pc = sub.add_parser("cost", help="운영 비용 측정")
    _common(pc)
    pc.set_defaults(func=cmd_cost)

    sub.add_parser("aggregate", help="결과 매트릭스 정리").set_defaults(func=cmd_aggregate)
    return p


def main():
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
