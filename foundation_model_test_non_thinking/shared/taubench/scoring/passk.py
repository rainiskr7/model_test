"""반복 시행 결과를 상류 정의 그대로 Pass^k 로 집계한다.

왜 필요한가: airline 20과제를 같은 모델·같은 프로토콜로 두 번 돌렸더니 통과 과제가
gemma 6건, qwen 4건 뒤집혔다. 건수는 13/13, 15/15 로 같았는데 **다른 과제를 맞혔다.**
한 번 돌린 Pass^1 로는 두 모델의 10점 차이가 실력 차인지 흔들림인지 가릴 수 없다.
상류가 4회 이상 시행을 권장하는 이유가 이것이다.

정의는 발명하지 않는다 — ``data/tau2-bench/src/tau2/metrics/agent_metrics.py`` 의
``pass_hat_k`` 와 같다::

    pass^k(과제) = C(성공 시행 수, k) / C(전체 시행 수, k)
    Pass^k        = 과제별 pass^k 의 평균

k=1 은 단순 성공률이고, k 가 커질수록 "매번 성공하는가" 를 묻는다. 한 번만 맞힌
과제는 k=2 에서 0 이 된다.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Iterable, Mapping

__all__ = ["task_success_counts", "pass_hat_k", "pass_hat_k_table"]


def task_success_counts(
    task_results: Iterable[Mapping[str, Any]],
) -> dict[str, tuple[int, int]]:
    """과제별 ``(성공 시행 수, 측정된 시행 수)``.

    측정되지 않은 시행(판정 필요·보상 누락·인프라 오류)은 분모에서 뺀다. 실패로
    세면 하네스 장애가 모델 점수로 둔갑하고, 성공으로 세면 그 반대다.
    """

    counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for result in task_results:
        if str(result.get("evaluation_status")) != "measured":
            continue
        entry = counts[str(result.get("task_id"))]
        entry[1] += 1
        if result.get("passed") is True:
            entry[0] += 1
    return {task_id: (success, total) for task_id, (success, total) in counts.items()}


def pass_hat_k(num_trials: int, success_count: int, k: int) -> float:
    """상류와 동일한 단일 과제 pass^k."""

    if num_trials < k:
        raise ValueError(f"trials {num_trials} < k {k}")
    return math.comb(success_count, k) / math.comb(num_trials, k)


def pass_hat_k_table(task_results: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """k=1..min(시행 수) 까지의 Pass^k.

    과제마다 시행 수가 다르면 **가장 적은 쪽**이 상한이다. 상류도 같은 규칙을 쓴다
    — 4회 돌린 과제 하나 때문에 2회짜리 과제에 k=4 를 물을 수는 없다.
    """

    counts = task_success_counts(task_results)
    if not counts:
        return {"tasks": 0, "max_k": 0, "pass_hat_k": {}}
    max_k = min(total for _, total in counts.values())
    table = {}
    for k in range(1, max_k + 1):
        table[f"pass^{k}"] = sum(
            pass_hat_k(total, success, k) for success, total in counts.values()
        ) / len(counts)
    return {
        "tasks": len(counts),
        "max_k": max_k,
        "trials_per_task": sorted({total for _, total in counts.values()}),
        "pass_hat_k": table,
    }
