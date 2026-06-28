"""MTEB 네이티브 번들 — 여러 태스크를 하나의 벤치마크 단위로 묶어 실행.

사용자 요청: "MTEB 활용해서 묶는 것도 가능?" → 두 가지 묶는 방식을 제공한다.

  (1) 우리 정의 태스크들을 한 번의 mteb.MTEB(tasks=[...]) 로 묶어 실행
      → mteb_runner.run_group / run_tasks 가 이미 이 방식(번들 실행)이다.

  (2) MTEB가 제공하는 공식 Benchmark 객체를 그대로 가져와 실행
      예: "MTEB(kor, v1)" 같은 한국어 벤치마크 묶음.
      official benchmark 는 태스크 구성이 mteb 측에서 관리되어 재현성이 높다.

NAMED_BUNDLES: 계획안의 그룹(스모크/한국어/금융)을 MTEB 번들로 노출.
"""

from __future__ import annotations

from .config import SMOKE_TASKS, KOREAN_TASKS, FINANCIAL_TASKS, TaskSpec
from .mteb_runner import _resolve_tasks, run_tasks

# 계획안 그룹 → TaskSpec 묶음
NAMED_BUNDLES: dict[str, list[TaskSpec]] = {
    "smoke": SMOKE_TASKS,
    "korean": KOREAN_TASKS,
    "financial": FINANCIAL_TASKS,
}


def list_official_benchmarks() -> list[str]:
    """mteb 가 제공하는 공식 벤치마크 이름 목록(한국어 묶음 탐색용)."""
    import mteb

    try:
        benches = mteb.get_benchmarks()
    except Exception as exc:
        print(f"[benchmarks] get_benchmarks 실패: {exc}")
        return []
    out = []
    for b in benches:
        out.append(getattr(b, "name", str(b)))
    return sorted(out)


def run_named_bundle(
    bundle_name: str,
    model_keys: list[str],
    prompt_modes: list[str],
    *,
    include_fallback: bool = False,
    overwrite: bool = False,
):
    """계획안 그룹(smoke/korean/financial)을 MTEB 번들로 묶어 실행."""
    if bundle_name not in NAMED_BUNDLES:
        raise KeyError(f"알 수 없는 번들: {bundle_name} (가능: {list(NAMED_BUNDLES)})")
    tasks = _resolve_tasks(NAMED_BUNDLES[bundle_name], include_fallback)
    return run_tasks(f"bundle_{bundle_name}", tasks, model_keys, prompt_modes,
                     overwrite=overwrite)


def run_official_benchmark(
    benchmark_name: str,
    model_keys: list[str],
    prompt_modes: list[str],
    *,
    overwrite: bool = False,
):
    """MTEB 공식 Benchmark 객체를 그대로 실행(예: 'MTEB(kor, v1)')."""
    import mteb

    bench = mteb.get_benchmark(benchmark_name)
    tasks = bench.tasks if hasattr(bench, "tasks") else list(bench)
    # 모델 루프/seed/encode_kwargs/정리는 run_tasks 에 위임(중복 제거, private import 제거).
    group = "official_" + benchmark_name.replace("/", "_").replace(" ", "")
    return run_tasks(group, tasks, model_keys, prompt_modes, overwrite=overwrite)
