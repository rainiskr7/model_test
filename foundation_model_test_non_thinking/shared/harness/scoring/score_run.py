#!/usr/bin/env python3
"""harness(KMMLU) 산출물의 발행 게이트와 파생 집계를 만든다.

이 산출물은 ``--log_samples`` 없이 만들어져 문항별 정오답 벡터가 없다. 그래서
``publish.claims.credential()`` 의 항목 벡터 경로로 재현성을 평가할 수 없고,
보고서는 집계값용 ``aggregate_credential()`` 만 사용한다. lm-eval의
``acc_stderr`` 는 문항이 모집단의 표본이라는 데서 오는 오차이지 재실행 변동이 아니다.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

SCORING_VERSION = "harness-kmmlu-v2"
HARNESS_DIR = Path(__file__).resolve().parent.parent
METRIC_KEY = "acc,none"
PROTOCOL_FIELDS = (
    "n_shot", "task_version", "lm_eval_version", "config_model", "max_length",
    "chat_template_sha", "metric_key", "model_name",
)


def expected_tasks(runner: Path | None = None) -> list[str]:
    """러너가 실제로 선언한 KMMLU 과목을 읽는다.

    채점기에 별도 목록을 두면 러너 변경이 조용히 다른 시험을 만든다.
    """

    path = Path(runner or HARNESS_DIR / "run_harness.sh")
    text = path.read_text(encoding="utf-8")
    block = re.search(r"^TASKS=\((.*?)^\)", text, re.S | re.M)
    if not block:
        raise ValueError(f"러너에서 TASKS 목록을 찾지 못했다: {path}")
    tasks = []
    for line in block.group(1).splitlines():
        match = re.fullmatch(r"\s*(kmmlu_[a-z0-9_]+)\s*(?:#.*)?", line)
        if match:
            tasks.append(match.group(1))
    if not tasks:
        raise ValueError(f"러너의 TASKS에 KMMLU 과목이 없다: {path}")
    return sorted(tasks)


def _run_identity(run_dir: Path) -> tuple[str, str]:
    """메타데이터가 없는 옛 산출물에만 경로 표기를 후퇴값으로 쓴다."""

    return run_dir.parents[2].name, run_dir.parents[1].name


def _subject(payload: Mapping[str, Any], task: str, result: Mapping[str, Any], fallback: str) -> dict[str, Any]:
    """정확도와 그 정확도가 같은 시험인지 판정할 규약을 함께 보존한다."""

    samples = (payload.get("n-samples") or {}).get(task) or {}
    configured = payload.get("config") or {}
    declared_name = payload.get("model_name")
    return {
        "task": task,
        "accuracy": result.get(METRIC_KEY),
        "sampling_stderr": result.get("acc_stderr,none"),
        "items": result.get("sample_len"),
        "items_original": samples.get("original"),
        "items_effective": samples.get("effective"),
        "n_shot": (payload.get("n-shot") or {}).get(task),
        "task_version": (payload.get("versions") or {}).get(task),
        "lm_eval_version": payload.get("lm_eval_version"),
        "config_model": configured.get("model"),
        "max_length": payload.get("max_length"),
        "chat_template_sha": payload.get("chat_template_sha"),
        "metric_key": METRIC_KEY if METRIC_KEY in result else None,
        "model_name": fallback if declared_name is None else declared_name,
        "model_name_fallback": declared_name is None,
    }


def load_run(run_dir: Path) -> dict[str, Any] | None:
    """한 세션의 과목 산출물과 읽기 실패를 섞지 않고 읽는다."""

    run_dir = Path(run_dir)
    directory_model, session = _run_identity(run_dir)
    subjects: dict[str, dict[str, Any]] = {}
    unreadable: list[str] = []
    duplicated: list[str] = []
    for path in sorted(run_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            unreadable.append(f"{path.name}: {type(exc).__name__}")
            continue
        results = payload.get("results") or {}
        if not isinstance(results, Mapping):
            unreadable.append(f"{path.name}: results가 객체가 아니다")
            continue
        for task, result in results.items():
            if not isinstance(result, Mapping):
                unreadable.append(f"{path.name}: {task} 결과가 객체가 아니다")
                continue
            if task in subjects:
                duplicated.append(task)
                continue
            subjects[task] = _subject(payload, task, result, directory_model)
    if not subjects and not unreadable:
        return None
    return {
        "path": str(run_dir),
        "source_path": f"{directory_model}/{session}",
        "directory_model": directory_model,
        "session": session,
        "subjects": subjects,
        "unreadable": unreadable,
        "duplicated": sorted(set(duplicated)),
    }


def _macro(subjects: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """과목 평균과 과목 사이 산포의 표준오차를 계산한다."""

    values = [float(entry["accuracy"]) for entry in subjects if entry.get("accuracy") is not None]
    if not values:
        return {"accuracy": None, "stderr": None, "subjects": 0}
    mean = sum(values) / len(values)
    if len(values) == 1:
        stderr = None
    else:
        variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
        stderr = math.sqrt(variance / len(values))
    return {"accuracy": mean, "stderr": stderr, "subjects": len(values)}


def _micro(subjects: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """문항 가중 평균과 전체 문항의 이항 표집 오차를 계산한다."""

    entries = [
        entry for entry in subjects
        if entry.get("accuracy") is not None and isinstance(entry.get("items"), int)
        and entry["items"] > 0
    ]
    total = sum(entry["items"] for entry in entries)
    if not total:
        return {"accuracy": None, "stderr": None, "items": 0}
    accuracy = sum(float(entry["accuracy"]) * entry["items"] for entry in entries) / total
    return {
        "accuracy": accuracy,
        "stderr": math.sqrt(max(accuracy * (1 - accuracy), 0.0) / total),
        "items": total,
    }


def _values(subjects: Iterable[Mapping[str, Any]], field: str) -> list[Any]:
    """프로토콜 불일치에서는 서로 다른 값을 모두 남긴다."""

    values: list[Any] = []
    for subject in subjects:
        value = subject.get(field)
        if value not in values:
            values.append(value)
    return values


def build_summary(run: Mapping[str, Any], expected: Iterable[str]) -> dict[str, Any]:
    """커버리지·규약·집계를 잃지 않는 런 요약을 만든다."""

    expected = sorted(expected)
    subjects = dict(run["subjects"])
    missing = [task for task in expected if task not in subjects]
    unexpected = sorted(task for task in subjects if task not in expected)
    ordered = [subjects[task] for task in expected if task in subjects]
    ordered.extend(subjects[task] for task in unexpected)
    names = _values(ordered, "model_name")
    model = str(names[0]) if len(names) == 1 and names[0] is not None else run["directory_model"]
    return {
        "scoring_version": SCORING_VERSION,
        "benchmark": "KMMLU (lm-eval-harness, 5-shot)",
        "model": model,
        "session": run["session"],
        "source_path": run["source_path"],
        "coverage": {
            "expected_subjects": len(expected), "measured_subjects": len(subjects),
            "missing": missing, "unexpected": unexpected,
        },
        "macro": _macro(ordered),
        "micro": _micro(ordered),
        "by_subject": ordered,
        "unreadable": list(run["unreadable"]),
        "duplicated": list(run["duplicated"]),
        "protocol": {field: _values(ordered, field) for field in PROTOCOL_FIELDS},
        "model_name_fallback": any(subject["model_name_fallback"] for subject in ordered),
    }


def _render_values(values: Iterable[Any]) -> str:
    return ", ".join(repr(value) for value in values)


def validate_summary(summary: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    """발행 차단과 기록상 경고를 분리한다.

    오래된 산출물에 ``chat_template_sha``가 일괄 누락된 사실은 규약이 갈렸다는
    뜻이 아니다. 이 게이트는 존재 여부가 아니라 과목 간 동일성을 판정한다.
    """

    failures: list[str] = []
    warnings: list[str] = []
    coverage = summary["coverage"]
    if summary["unreadable"]:
        failures.append(
            f"읽지 못한 산출물이 있다 ({len(summary['unreadable'])}건) — "
            "커버리지 누락과 읽기 실패를 구별할 수 없다"
        )
    if summary["duplicated"]:
        failures.append(
            f"같은 과목이 여러 파일에 있다: {', '.join(summary['duplicated'])} — "
            "어느 값이 이 런인지 산출물이 말하지 않는다"
        )
    if coverage["missing"] or coverage["unexpected"]:
        pieces = []
        if coverage["missing"]:
            pieces.append(f"누락 {len(coverage['missing'])}개")
        if coverage["unexpected"]:
            pieces.append(f"예상 밖 {len(coverage['unexpected'])}개")
        failures.append(
            f"과목 집합이 러너 TASKS와 다르다 ({coverage['measured_subjects']}/"
            f"{coverage['expected_subjects']}; {', '.join(pieces)}) — 커버리지가 다르면 같은 시험이 아니다"
        )
    for field, values in summary["protocol"].items():
        if len(values) != 1:
            failures.append(f"프로토콜 {field} 값이 과목마다 갈린다: {_render_values(values)}")
    shots = summary["protocol"]["n_shot"]
    if len(shots) == 1 and shots[0] != 5:
        failures.append(f"n-shot이 5가 아니다: {shots[0]!r}")
    for entry in summary["by_subject"]:
        if entry.get("accuracy") is None:
            failures.append(f"{entry['task']}: 메트릭 키 {METRIC_KEY!r}가 없다")
        if not isinstance(entry.get("items"), int) or entry["items"] <= 0:
            failures.append(f"{entry['task']}: sample_len이 양의 정수가 아니다")
        if entry.get("items_original") and entry.get("items_effective") != entry.get("items_original"):
            warnings.append(
                f"{entry['task']}: 문항 {entry.get('items_effective')}/"
                f"{entry.get('items_original')}만 채점됐다"
            )
    # 필드가 **통째로 없는 것**과 값이 일치하는 것은 다르다. 프로토콜 게이트는
    # 디렉토리 안의 값이 서로 같은지만 보므로, 전부 None 이면 "일치"로 통과한다.
    # 그러나 기록이 없으면 그 프로토콜이 다른 런과 같았는지 감사할 수 없다.
    # 실측: chat_template_sha 가 통째로 없는 런이 4개이고 그중 2개가 표에 실린다.
    # 이 세션 내내 지킨 규율과 같다 — 기록의 부재를 같음의 증거로 쓰지 않는다.
    for field in PROTOCOL_FIELDS:
        values = summary["protocol"].get(field) or []
        if values and all(value is None for value in values):
            warnings.append(
                f"{field} 기록이 없다 — 이 런의 해당 프로토콜은 다른 런과 같았는지 감사할 수 없다"
            )

    if summary["model_name_fallback"]:
        warnings.append("model_name이 없어 디렉터리 이름으로 모델 정체성을 기록했다")
    return failures, warnings


def score_run(run_dir: Path, expected: Iterable[str] | None = None) -> dict[str, Any] | None:
    """한 세션을 읽고 ``publish_status`` 계약을 붙인다."""

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


def measurement_digest(summary: Mapping[str, Any]) -> str:
    """동일 기록 집계 벡터를 식별하는 지문이다.

    결정적 재실행도 같은 지문을 낼 수 있다. 그래서 접힌 경로는 중복 표시일 뿐
    k=2나 분산 0의 증거가 아니며 재현성 계산에 사용하면 안 된다.
    """

    material = {
        "subjects": [
            [entry["task"], entry.get("accuracy"), entry.get("items"), entry.get("n_shot"), entry.get("task_version")]
            for entry in sorted(summary["by_subject"], key=lambda entry: entry["task"])
        ],
        # 서로 다른 model_name 표기는 같은 기록 사본에도 있으므로 경로별 중복 접기에는
        # 넣지 않는다. 한 디렉터리 안의 model_name 불일치는 위 게이트가 별도로 막는다.
        "protocol": {
            field: summary["protocol"][field]
            for field in PROTOCOL_FIELDS if field != "model_name"
        },
    }
    serialized = json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]


def subject_set_digest(summary: Mapping[str, Any]) -> str:
    """같은 과목 수라도 과목 정체성이 다르면 비교를 막을 지문이다."""

    material = "\n".join(sorted(entry["task"] for entry in summary["by_subject"]))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def group_duplicates(summaries: Iterable[Mapping[str, Any]]) -> dict[str, list[Mapping[str, Any]]]:
    """같은 지문을 경로별로 묶는다. 이 묶음은 반복 런 수가 아니다."""

    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for summary in summaries:
        grouped.setdefault(measurement_digest(summary), []).append(summary)
    return grouped
