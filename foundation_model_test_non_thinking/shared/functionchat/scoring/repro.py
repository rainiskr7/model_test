"""반복 실행의 재현성을 항목 단위로 대조한다.

이 저장소에는 이미 반복 런이 있는데(gemma 3개, qwen 4개) 아무도 산포를 내지 않았다.
실측하면 이렇다 — 같은 600문항, 같은 scoring_version:

    qwen   553, 553, 553, 553   건수 동일
    gemma  536, 534, 537        건수 산포 3

**건수가 같다고 같은 측정은 아니다.** taubench airline 에서 통과 건수가 13/13,
15/15 로 같은데 통과한 과제가 4~6건 뒤집힌 사례를 겪었다. 그래서 여기서도 건수가
아니라 **통과 항목 집합**을 본다.

코호트는 `(scoring_version, dataset, 항목 집합 digest, 모델)` 이다. scoring_version
v1(600문항)과 v2(670문항)는 다른 측정이므로 섞지 않는다.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

try:  # 패키지로 임포트될 때
    from .exact_match import exact_match
    from .score_run import scorable_status
except ImportError:  # 파일 하나만 단독 로드할 때
    import sys as _sys

    _sys.path.insert(0, str(Path(__file__).resolve().parent))
    from exact_match import exact_match
    from score_run import scorable_status

__all__ = ["load_run", "cohort_key", "passed_item_ids", "reproducibility_report"]

DATASET_FILES = ("singlecall", "call_decision", "dialog")


def _digest(values: Iterable[str]) -> str:
    material = "\n".join(sorted(values)).encode("utf-8")
    return hashlib.sha256(material).hexdigest()[:16]


def load_run(run_dir: Path) -> dict[str, Any] | None:
    """한 런의 요약과 항목별 판정을 모은다. 읽을 수 없으면 None."""

    run_dir = Path(run_dir)
    try:
        summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    except Exception:
        return None
    items: dict[str, bool] = {}
    unreadable: list[str] = []
    for name in DATASET_FILES:
        path = run_dir / f"{name}.json"
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            # 조용히 넘어가면 항목 집합이 줄어 코호트가 갈리고, 그 결과가
            # "비교 대상이 없다"(UNVERIFIED)로 나온다 — 읽기 실패가 재현성 결론으로
            # 둔갑하는 것이다. 사유를 들고 간다.
            unreadable.append(f"{path.name}: {type(exc).__name__}")
            continue
        for record in payload.get("results") or []:
            # 채점 자격은 채점기가 정한다. `evaluation_status` 만 보면 안 된다 —
            # 그 필드는 "exact 채점 대상인지" 만 나타내고, API 실패로 응답이 비어
            # 있는 항목은 여전히 measured 로 남는다. 그대로 세면 타임아웃 하나가
            # 모델 오답 하나로 둔갑한다.
            if scorable_status(record) != "scorable":
                continue
            # 산출물의 `exact_match` 필드는 비어 있다(실측: 500건 전부 None).
            # 통과 여부는 채점기가 계산하는 값이므로 **같은 채점기로 다시 계산한다** —
            # 저장된 파생 필드를 믿으면 그 필드를 만든 코드의 결함을 그대로 물려받는다.
            items[str(record.get("item_id"))] = exact_match(
                dict(record), record.get("model_output")
            )
    return {
        "session": run_dir.parents[1].name,
        "model": str(summary.get("model")),
        "scoring_version": str(summary.get("scoring_version")),
        "publishable": bool((summary.get("publish_status") or {}).get("publishable")),
        "items": items,
        "unreadable_datasets": unreadable,
    }


def cohort_key(run: Mapping[str, Any]) -> tuple[str, str, str]:
    """같은 모델을 같은 규약으로 다시 잰 것만 묶는다.

    항목 집합 digest 를 넣는 이유: scoring_version 이 같아도 커버리지가 다르면 다른
    측정이다. 이름이 아니라 실제로 무엇을 쟀는지가 정체성이다.
    """

    return (
        run["scoring_version"],
        _digest(run["items"].keys()),
        run["model"],
    )


def passed_item_ids(run: Mapping[str, Any]) -> set[str]:
    return {item_id for item_id, passed in run["items"].items() if passed}


def reproducibility_report(runs: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for run in runs:
        grouped[cohort_key(run)].append(run)

    # 같은 (모델, scoring_version) 인데 항목 집합만 달라 갈라진 경우를 찾는다.
    # 그대로 두면 "비교 대상이 없다" 로만 보여서, 커버리지가 달랐다는 사실이 사라진다.
    by_measurement: dict[tuple[str, str], set[str]] = defaultdict(set)
    for (scoring_version, digest, model) in grouped:
        by_measurement[(scoring_version, model)].add(digest)

    report: list[dict[str, Any]] = []
    for (scoring_version, digest, model), members in sorted(grouped.items()):
        sessions = [str(run["session"]) for run in members]
        unreadable = sorted({name for run in members for name in run.get("unreadable_datasets") or []})
        if len(members) < 2:
            siblings = by_measurement[(scoring_version, model)]
            reason = "이 규약으로 이 모델을 한 번만 돌렸다 — 비교 대상이 없다"
            if len(siblings) > 1:
                reason = (
                    f"같은 scoring_version 의 런이 더 있으나 채점 항목 집합이 달라 "
                    f"코호트가 {len(siblings)}개로 갈렸다 — 커버리지가 다르면 같은 측정이 아니다"
                )
            if unreadable:
                reason += f" (읽지 못한 산출물: {', '.join(unreadable)})"
            report.append({
                "model": model, "scoring_version": scoring_version, "item_digest": digest,
                "runs": sessions, "status": "UNVERIFIED", "reason": reason,
                "unreadable_datasets": unreadable,
            })
            continue
        sets = [passed_item_ids(run) for run in members]
        counts = [len(s) for s in sets]
        unstable = set().union(*sets) - set.intersection(*sets)
        report.append({
            "model": model, "scoring_version": scoring_version, "item_digest": digest,
            "runs": sessions,
            "status": "IDENTICAL" if not unstable else "DIVERGED",
            "passed_counts": counts,
            "count_spread": max(counts) - min(counts),
            "stable_passed": len(set.intersection(*sets)),
            "unstable_items": sorted(unstable),
            "reason": (
                None
                if not unstable
                else f"통과 항목이 런마다 다르다 ({len(unstable)}건). "
                "건수가 같아도 다른 항목을 맞힌 것이면 같은 측정이 아니다"
            ),
        })
    return report
