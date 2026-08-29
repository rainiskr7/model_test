"""agent 트랙 반복 런의 항목별 통과 벡터를 보존해 클레임 자격을 만든다.

레벨 점수나 전체 평균은 서로 다른 과제가 뒤집혀도 같을 수 있다. 이 모듈은 각
``L*.json`` 의 task_id 를 레벨과 함께 보관해, 기록된 과제별 성공 여부만 비교한다.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

try:  # 패키지로 임포트될 때
    from ...publish.claims import comparable, credential
except ImportError:  # 점수 모듈을 파일 경로로 직접 로드하는 테스트일 때
    import sys as _sys

    _sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from publish.claims import comparable, credential

__all__ = [
    "load_run",
    "cohort_key",
    "reproducibility_report",
]


def _digest(values: Iterable[str]) -> str:
    material = "\n".join(sorted(values)).encode("utf-8")
    return hashlib.sha256(material).hexdigest()[:16]


def _identity(values: Iterable[Any]) -> Any:
    """기록된 값 하나는 그대로, 런 내부 불일치는 구별 가능한 값으로 남긴다."""

    encoded = {
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for value in values
    }
    if not encoded:
        return None
    decoded = [json.loads(value) for value in sorted(encoded)]
    return decoded[0] if len(decoded) == 1 else tuple(sorted(encoded))


def load_run(run_dir: Path) -> dict[str, Any] | None:
    """한 agent 런의 레벨별 성공 여부와 그 실행 규약을 읽는다."""

    run_dir = Path(run_dir)
    items: dict[str, bool] = {}
    metadata: list[Mapping[str, Any]] = []
    found = False
    for path in sorted(run_dir.glob("L*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            # 일부 레벨을 읽지 못했는데 빈 벡터로 보고하면 커버리지 손실이 안정성으로
            # 바뀐다. 런 전체를 코호트에 넣지 않아 결측을 발행 근거로 쓰지 않는다.
            return None
        found = True
        level = path.stem
        entry_metadata = payload.get("metadata")
        if isinstance(entry_metadata, Mapping):
            metadata.append(entry_metadata)
        for record in payload.get("results") or []:
            if not isinstance(record, Mapping) or "task_id" not in record or "success" not in record:
                continue
            items[f"{level}:{record['task_id']}"] = bool(record["success"])

    if not found:
        return None
    decoding = [entry.get("decoding") for entry in metadata if isinstance(entry.get("decoding"), Mapping)]
    removed = {
        tuple(sorted(str(value) for value in (entry.get("constraints") or {}).get("removed_parameters") or []))
        for entry in decoding
    }
    return {
        "session": run_dir.parents[1].name,
        "track": run_dir.name,
        "model": _identity([entry.get("model") for entry in metadata if "model" in entry]),
        "items": items,
        "native_tool_calling": _identity(
            [entry.get("native_tool_calling") for entry in metadata if "native_tool_calling" in entry]
        ),
        # 디코딩 기록이 없는 산출물은 제약이 없었다는 뜻이 아니다.
        "removed_parameters": None if not decoding else tuple(sorted(removed)),
    }


def cohort_key(run: Mapping[str, Any]) -> tuple[Any, ...]:
    """도구 호출 경로와 항목 집합이 같은 반복 런만 한 코호트로 묶는다."""

    return (
        run.get("track"),
        run.get("model"),
        run.get("native_tool_calling"),
        run.get("removed_parameters"),
        _digest((run.get("items") or {}).keys()),
    )


def reproducibility_report(runs: Iterable[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """코호트별 자격과 같은 기록 규약 안의 모델 비교만 돌려준다."""

    grouped: dict[tuple[Any, ...], list[Mapping[str, Any]]] = defaultdict(list)
    for run in runs:
        grouped[cohort_key(run)].append(run)

    credentials: list[dict[str, Any]] = []
    for key, members in sorted(grouped.items(), key=lambda entry: repr(entry[0])):
        track, model, native_tool_calling, removed_parameters, item_digest = key
        credentials.append({
            "track": track,
            "model": model,
            "native_tool_calling": native_tool_calling,
            "removed_parameters": removed_parameters,
            "item_digest": item_digest,
            "credential": credential([
                {"run_id": str(member.get("session")), "items": member.get("items") or {}}
                for member in members
            ]),
        })

    comparisons: list[dict[str, Any]] = []
    by_protocol: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for entry in credentials:
        by_protocol[(
            entry["track"], entry["native_tool_calling"],
            entry["removed_parameters"], entry["item_digest"],
        )].append(entry)
    for entries in by_protocol.values():
        for index, left in enumerate(entries):
            for right in entries[index + 1:]:
                comparisons.append({
                    "left": left["model"],
                    "right": right["model"],
                    "verdict": comparable(left["credential"], right["credential"]),
                })
    return {"credentials": credentials, "comparisons": comparisons}
