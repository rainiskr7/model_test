#!/usr/bin/env python3
"""harness(lm-eval KMMLU) 런을 벤치마크 형식으로 채점한다.

**단일 100점 만점 숫자를 만들지 않는다.** 이 트랙의 산출물은 과목마다 독립된
정확도이고, 그것을 하나의 수로 접으면 세 가지가 한꺼번에 사라진다 — 몇 과목을
돌렸는지, 과목마다 몇 문항이었는지, 그 정확도의 표집 오차가 얼마인지.

실제로 그 셋이 사라지면 어떻게 되는지 이 저장소에 있다:

    meta_models_Muse_Glimmer_30B   16/46 과목  12,130문항  매크로 0.643
    gemma_4_26b_a4b_it             45/46 과목  35,030문항  매크로 0.653

두 수를 나란히 놓으면 "거의 비슷하다"로 읽히지만 **다른 시험을 본 것**이다.
그래서 이 채점기는 커버리지가 다르면 발행을 막는다.

## 두 평균을 모두 낸다

``macro`` 는 과목을 단위로 한 평균이고 ``micro`` 는 문항을 단위로 한 평균이다.
과목별 문항 수가 다르면 둘이 갈라진다(KMMLU 는 과목마다 문항 수가 다르다).
어느 하나가 "진짜"가 아니라 서로 다른 질문에 답하는 값이므로 둘 다 낸다.

## 표집 오차와 재현성은 다른 것이다

lm-eval 은 과목마다 ``acc_stderr`` 를 준다. 이것은 **같은 문항으로 다시 채점했을
때의 오차가 아니라, 이 문항들이 모집단의 표본이라는 데서 오는 오차**다. 모델을
다시 돌렸을 때 답이 뒤집히는 재현성은 별개이며 이 트랙에서는 아직 측정되지
않았다(모델마다 런이 하나뿐이다). 두 불확실성을 한 칸에 넣지 않는다.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

SCORING_VERSION = "harness-kmmlu-v1"

HARNESS_DIR = Path(__file__).resolve().parent.parent


def expected_tasks(runner: Path | None = None) -> list[str]:
    """러너가 돌리기로 선언한 과목 목록.

    별도 상수로 베끼면 러너와 채점기가 조용히 어긋난다. 러너를 읽는다.
    """

    path = Path(runner or (HARNESS_DIR / "run_harness.sh"))
    text = path.read_text(encoding="utf-8")
    block = re.search(r"^TASKS=\((.*?)^\)", text, re.S | re.M)
    if not block:
        raise ValueError(f"러너에서 TASKS 목록을 찾지 못했다: {path}")
    return sorted(re.findall(r"^\s*([a-z0-9_]+)\s*$", block.group(1), re.M))


def load_run(run_dir: Path) -> dict[str, Any] | None:
    """한 런의 과목별 결과. 읽을 수 없으면 None."""

    run_dir = Path(run_dir)
    subjects: dict[str, dict[str, Any]] = {}
    unreadable: list[str] = []
    duplicated: list[str] = []
    for path in sorted(run_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            # 조용히 넘어가면 커버리지가 줄어 "덜 돌린 런"으로 보인다. 읽기 실패와
            # 실행 안 함은 다른 사실이다.
            unreadable.append(f"{path.name}: {type(exc).__name__}")
            continue
        for task, entry in (payload.get("results") or {}).items():
            accuracy = entry.get("acc,none")
            if accuracy is None:
                continue
            if task in subjects:
                duplicated.append(task)
                continue
            samples = (payload.get("n-samples") or {}).get(task) or {}
            subjects[task] = {
                "task": task,
                "accuracy": float(accuracy),
                # 표집 오차. 재현성이 아니다 — 독스트링 참조.
                "sampling_stderr": entry.get("acc_stderr,none"),
                "items": int(entry.get("sample_len") or samples.get("effective") or 0),
                "items_original": samples.get("original"),
                "items_effective": samples.get("effective"),
                "n_shot": (payload.get("n-shot") or {}).get(task),
            }
    if not subjects and not unreadable:
        return None
    return {
        "session": run_dir.parents[1].name,
        "model": run_dir.parents[2].name,
        "subjects": subjects,
        "unreadable": unreadable,
        "duplicated": sorted(set(duplicated)),
    }


def _macro(subjects: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """과목을 단위로 한 평균. 표준오차는 과목 간 산포에서 온다."""

    values = [entry["accuracy"] for entry in subjects]
    if not values:
        return {"accuracy": None, "stderr": None, "subjects": 0}
    mean = sum(values) / len(values)
    if len(values) < 2:
        stderr = None
    else:
        variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
        stderr = math.sqrt(variance / len(values))
    return {"accuracy": mean, "stderr": stderr, "subjects": len(values)}


def _micro(subjects: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """문항을 단위로 한 평균. 표준오차는 이항 표집에서 온다."""

    entries = [entry for entry in subjects if entry["items"]]
    total = sum(entry["items"] for entry in entries)
    if not total:
        return {"accuracy": None, "stderr": None, "items": 0}
    correct = sum(entry["accuracy"] * entry["items"] for entry in entries)
    accuracy = correct / total
    return {
        "accuracy": accuracy,
        "stderr": math.sqrt(max(accuracy * (1 - accuracy), 0.0) / total),
        "items": total,
    }


def build_summary(run: Mapping[str, Any], expected: Iterable[str]) -> dict[str, Any]:
    expected = sorted(expected)
    subjects = run["subjects"]
    missing = [task for task in expected if task not in subjects]
    unexpected = sorted(task for task in subjects if task not in expected)

    ordered = [subjects[task] for task in expected if task in subjects]
    ordered += [subjects[task] for task in unexpected]

    return {
        "scoring_version": SCORING_VERSION,
        "benchmark": "KMMLU (lm-eval-harness, 5-shot)",
        "model": run["model"],
        "session": run["session"],
        "coverage": {
            "expected_subjects": len(expected),
            "measured_subjects": len(subjects),
            "missing": missing,
            "unexpected": unexpected,
        },
        # 두 평균을 모두 낸다. 하나만 내면 과목 크기 차이가 사라진다.
        "macro": _macro(ordered),
        "micro": _micro(ordered),
        "by_subject": ordered,
        "unreadable": run.get("unreadable") or [],
        "duplicated": run.get("duplicated") or [],
    }


def measurement_digest(summary: Mapping[str, Any]) -> str:
    """과목별 정확도 벡터의 지문.

    같은 산출물이 여러 디렉토리에 복사돼 있다. 실측: `gemma_4_31b_it`,
    `google_gemma_4_31B_it`(세션 2개), 그리고 `.bad` 사본까지 **같은 수치**가 네 줄로
    나온다. 그대로 표에 실으면 한 번 잰 것이 네 번 잰 것처럼 보이고, 순위표에서
    그 모델의 존재감이 부풀려진다.

    모델 이름이나 경로가 아니라 **잰 값**으로 같은 측정을 식별한다 — 디렉토리
    표기(대소문자·접두사·``.bad``)는 측정과 무관하다.
    """

    material = "\n".join(
        f"{entry['task']}={entry['accuracy']!r}:{entry['items']}"
        for entry in sorted(summary["by_subject"], key=lambda item: item["task"])
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def group_duplicates(summaries: Iterable[Mapping[str, Any]]) -> dict[str, list[Mapping[str, Any]]]:
    """같은 측정 지문을 가진 런들을 묶는다."""

    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for summary in summaries:
        grouped.setdefault(measurement_digest(summary), []).append(summary)
    return grouped


def validate_summary(summary: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    """발행 가능 여부. (failures, warnings)"""

    failures: list[str] = []
    warnings: list[str] = []
    coverage = summary["coverage"]

    if summary["unreadable"]:
        failures.append(
            f"읽지 못한 산출물이 있다 ({len(summary['unreadable'])}건) — "
            "커버리지 손실인지 실행 누락인지 구분할 수 없다"
        )
    if summary["duplicated"]:
        failures.append(
            f"같은 과목이 여러 파일에 있다: {', '.join(summary['duplicated'])} — "
            "어느 것이 이 런의 값인지 산출물이 말하지 않는다"
        )
    if coverage["missing"]:
        # 이것이 이 트랙의 핵심 게이트다. 16과목 평균과 45과목 평균을 같은 열에
        # 올리면 "다른 시험을 본 두 수"를 비교하게 된다.
        failures.append(
            f"과목 {len(coverage['missing'])}개가 빠졌다 "
            f"({coverage['measured_subjects']}/{coverage['expected_subjects']}) — "
            f"커버리지가 다르면 같은 시험이 아니다: {', '.join(coverage['missing'][:5])}"
            + (" …" if len(coverage["missing"]) > 5 else "")
        )
    if coverage["unexpected"]:
        warnings.append(
            f"러너가 선언하지 않은 과목이 있다: {', '.join(coverage['unexpected'])}"
        )
    for entry in summary["by_subject"]:
        if entry["items_original"] and entry["items_effective"] != entry["items_original"]:
            warnings.append(
                f"{entry['task']}: 문항 {entry['items_effective']}/{entry['items_original']} 만 채점됐다"
            )
    return failures, warnings


def score_run(run_dir: Path, expected: Iterable[str] | None = None) -> dict[str, Any] | None:
    run = load_run(run_dir)
    if run is None:
        return None
    summary = build_summary(run, expected if expected is not None else expected_tasks())
    failures, warnings = validate_summary(summary)
    summary["publish_status"] = {
        "publishable": not failures,
        "failures": failures,
        "warnings": warnings,
        "gate_scoring_version": SCORING_VERSION,
    }
    return summary
