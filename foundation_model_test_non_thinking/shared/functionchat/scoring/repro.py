"""반복 실행의 재현성을 항목 단위로 대조한다.

이 저장소에는 이미 반복 런이 있는데(gemma 3개, qwen 4개) 아무도 산포를 내지 않았다.
실측하면 이렇다 — 같은 600문항, 같은 scoring_version:

    qwen   553, 553, 553, 553   건수 동일
    gemma  536, 534, 537        건수 산포 3

**건수가 같다고 같은 측정은 아니다.** taubench airline 에서 통과 건수가 13/13,
15/15 로 같은데 통과한 과제가 4~6건 뒤집힌 사례를 겪었다. 그래서 여기서도 건수가
아니라 **통과 항목 집합**을 본다.

코호트는 scoring_version, 항목 집합, 모델과 산출물이 기록한 실행 규약이다.
같은 점수라도 native tool 호출·시간 제한·디코딩 제약이 다르면 같은 측정이 아니다.
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

__all__ = [
    "load_run", "cohort_key", "passed_item_ids", "reproducibility_report",
    "judge_credential",
]

DATASET_FILES = ("singlecall", "call_decision", "dialog")


def _digest(values: Iterable[str]) -> str:
    material = "\n".join(sorted(values)).encode("utf-8")
    return hashlib.sha256(material).hexdigest()[:16]


def _metadata_identity(values: Iterable[Any]) -> Any:
    """한 런 안에서 기록된 메타데이터를 비교 가능한 값으로 보존한다."""

    encoded = {
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for value in values
    }
    if not encoded:
        return None
    decoded = [json.loads(value) for value in sorted(encoded)]
    return decoded[0] if len(decoded) == 1 else tuple(sorted(encoded))


def load_run(run_dir: Path) -> dict[str, Any] | None:
    """한 런의 요약과 항목별 판정을 모은다. 읽을 수 없으면 None."""

    run_dir = Path(run_dir)
    try:
        summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    except Exception:
        return None
    items: dict[str, bool] = {}
    unreadable: list[str] = []
    metadata: list[Mapping[str, Any]] = []
    timeouts_observed = False
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
        record_metadata = payload.get("metadata")
        if isinstance(record_metadata, Mapping):
            metadata.append(record_metadata)
        for record in payload.get("results") or []:
            if not timeouts_observed:
                # 산출물에 남은 실패 사유에서 타임아웃 흔적을 찾는다. 하나라도
                # 있으면 그 런에서는 타임아웃 값이 결과를 바꿨을 수 있다.
                blob = json.dumps(record, ensure_ascii=False).lower()
                if "timeout" in blob or "timed out" in blob:
                    timeouts_observed = True
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
    # 디코딩 프로비넌스는 데이터셋 산출물의 metadata 에 있다. 없으면(계약 이전
    # 산출물) None — "제어됐다"고 단정하지 않는다.
    # 첫 데이터셋에서 멈추지 않는다. 데이터셋마다 다른 제약으로 돌았다면 그
    # 사실 자체가 중요한데, 하나만 보고 끝내면 나머지가 사라진다.
    removed_sets: list[frozenset] = []
    for record_metadata in metadata:
        decoding = record_metadata.get("decoding")
        if isinstance(decoding, dict) and decoding.get("available"):
            removed_sets.append(
                frozenset((decoding.get("constraints") or {}).get("removed_parameters") or [])
            )
    removed = sorted(set().union(*removed_sets)) if removed_sets else []
    # 기록이 없으면(계약 이전 산출물) None — "제거되지 않았다" 고 단정하지 않는다.
    controls_removed = ("temperature" in removed) if removed_sets else None

    return {
        "session": run_dir.parents[1].name,
        "model": str(summary.get("model")),
        # 타임아웃이 실제로 걸렸는가. 기록은 항상 남기고, 코호트 정체성에는
        # 걸렸을 때만 쓴다 — cohort_key 의 주석 참조.
        "timeouts_observed": timeouts_observed,
        "sampling_controls_removed": controls_removed,
        "removed_sampling_params": removed,
        # 없는 필드는 기존 산출물의 미기록 상태다. False/0/빈 문자열로 바꾸면
        # 기록된 프로토콜과 기록되지 않은 프로토콜을 같은 코호트로 오인한다.
        "native_tool_calling": _metadata_identity(
            [entry.get("native_tool_calling") for entry in metadata if "native_tool_calling" in entry]
        ),
        "request_timeout": _metadata_identity(
            [entry.get("request_timeout") for entry in metadata if "request_timeout" in entry]
        ),
        "task_timeout": _metadata_identity(
            [entry.get("task_timeout") for entry in metadata if "task_timeout" in entry]
        ),
        "removed_parameters": (
            None
            if not removed_sets
            else tuple(sorted(tuple(sorted(values)) for values in removed_sets))
        ),
        "endpoint": _metadata_identity(
            [entry.get("endpoint") for entry in metadata if "endpoint" in entry]
        ),
        "scoring_version": str(summary.get("scoring_version")),
        "publishable": bool((summary.get("publish_status") or {}).get("publishable")),
        "items": items,
        "unreadable_datasets": unreadable,
    }


def cohort_key(run: Mapping[str, Any]) -> tuple[Any, ...]:
    """같은 모델을 같은 규약으로 다시 잰 것만 묶는다.

    항목 집합 digest 를 넣는 이유: scoring_version 이 같아도 커버리지가 다르면 다른
    측정이다. 이름이 아니라 실제로 무엇을 쟀는지가 정체성이다.

    **타임아웃은 실제로 걸렸을 때만 규약의 일부다.** 한 건도 걸리지 않았다면 그
    값은 결과에 아무 영향을 주지 않은 no-op 이고, 그것으로 코호트를 가르면 같은
    측정이 둘로 쪼개진다. 실측으로 확인한 사례: qwen 5런 중 하나만 task_timeout 이
    600s(나머지 900s)였는데 타임아웃은 한 건도 없었다. 그런데도 키에 넣자 코호트가
    k=4 와 k=1 로 갈렸고, **뒤집힌 항목 10건이 0건으로 사라졌다** — 이 계층이
    존재하는 이유였던 관측이 통째로 안 보이게 된 것이다.

    같은 원리가 이 저장소의 multimodal 에도 있다
    (``shared/multimodal/publish/schema.py`` 의 ``_is_noop_serving_constraints``).
    """

    return (
        run["scoring_version"],
        _digest(run["items"].keys()),
        run["model"],
        run.get("native_tool_calling"),
        # 걸리지 않은 타임아웃은 기록만 하고 정체성에서 뺀다.
        run.get("request_timeout") if run.get("timeouts_observed") else None,
        run.get("task_timeout") if run.get("timeouts_observed") else None,
        run.get("removed_parameters"),
        run.get("endpoint"),
    )


def passed_item_ids(run: Mapping[str, Any]) -> set[str]:
    return {item_id for item_id, passed in run["items"].items() if passed}


def judge_credential(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """한 judge 런의 내부 표 갈림으로 판정 축의 클레임 자격을 만든다.

    judge 는 항목마다 3표를 남긴다. 따라서 외부 반복 런이 하나여도 ``unstable``
    기록에서 판정기의 관측된 흔들림을 셀 수 있다. exact-match 항목 벡터와 합치면
    다른 채점기와 다른 측정을 한 예산으로 보게 되므로 이 값은 judge 축 전용이다.
    """

    measured = [
        record for record in records
        if record.get("status") == "judged" and record.get("verdict") in {"pass", "fail"}
    ]
    passed = sum(record.get("verdict") == "pass" for record in measured)
    unstable = [
        str(record.get("serial_num") or record.get("item_id") or index)
        for index, record in enumerate(measured, start=1)
        if record.get("unstable") is True
    ]
    return {
        # 이 축에서 k=1 은 단일 모델 실행 횟수다. repeatability_observed 인 이유는
        # 각 항목의 3표가 이미 서로 다른 판정을 낼 수 있는지 관측했기 때문이다.
        "claim_class": "repeatability_observed",
        "k": 1,
        "measured_items": len(measured),
        "pass_counts": [passed],
        "count_range": [passed, passed],
        "majority_passed": passed,
        "unstable_items": unstable,
        "instability_envelope": [passed - len(unstable), passed + len(unstable)],
        "reason": "항목별 3표의 갈림을 런 내부에서 관측한 judge 축이다",
    }


def reproducibility_report(runs: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[Mapping[str, Any]]] = defaultdict(list)
    for run in runs:
        grouped[cohort_key(run)].append(run)

    # 같은 (모델, scoring_version) 인데 항목 집합만 달라 갈라진 경우를 찾는다.
    # 그대로 두면 "비교 대상이 없다" 로만 보여서, 커버리지가 달랐다는 사실이 사라진다.
    by_measurement: dict[tuple[str, str], set[str]] = defaultdict(set)
    for scoring_version, digest, model, *_ in grouped:
        by_measurement[(scoring_version, model)].add(digest)

    report: list[dict[str, Any]] = []
    for key, members in sorted(grouped.items(), key=lambda entry: repr(entry[0])):
        scoring_version, digest, model = key[:3]
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
            # 흔들림이 우연인지 구조적인지 구분한다. diffusion 백엔드는
            # temperature 를 거부하므로 **샘플링 제어 수단 자체가 없다** — 그때
            # 반복 실행이 달라지는 것은 모델 결함이 아니라 정상이고, 그 모델의
            # 단일 런 숫자는 인용하면 안 된다. (nlu 실측: 요청 바이트가 동일한
            # 5런에서 한 항목이 세 갈래로 갈렸다.)
            "sampling_controls_removed": (
                None
                if any(run.get("sampling_controls_removed") is None for run in members)
                else any(run.get("sampling_controls_removed") for run in members)
            ),
            "removed_sampling_params": sorted({
                param for run in members for param in run.get("removed_sampling_params") or []
            }),
        })
    return report
