"""nlu 런을 항목별 pass/fail 벡터로 채점한다.

**점수도 순위도 만들지 않는다.** 프롬프트 2개(항목 5개)는 스칼라 점수를 지탱하지
못한다 — 평균을 내는 순간 없는 신뢰도를 지어내는 것이다. 여기서 나오는 것은
항목별 판정 벡터와, 그 벡터를 어떻게 읽어야 하는지에 필요한 사실들뿐이다.

특히 두 가지를 함께 낸다.
- **변별하지 못한 항목** — 모든 모델이 같은 답을 낸 항목은 모델을 가르지 못한다.
- **상수 전략 기준선** — 항상 같은 라벨만 답해서 얻을 수 있는 최대 통과 수.
  이것을 함께 보지 않으면 5개 중 3개 통과가 실력처럼 보인다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

try:  # 패키지로 임포트될 때
    from .contract import items_for, load_answer_key, load_contract, parse_answers
except ImportError:  # 파일 하나만 단독 로드할 때
    import sys as _sys

    _sys.path.insert(0, str(Path(__file__).resolve().parent))
    from contract import items_for, load_answer_key, load_contract, parse_answers

__all__ = ["score_item", "score_run", "load_run_records", "discrimination", "constant_baseline"]

SCORING_VERSION = "nlu-v1"


def score_item(item: Mapping[str, Any], answers: Mapping[str, str], expected: str) -> dict[str, Any]:
    """한 항목의 판정.

    ``invalid`` 는 오답이 아니다. 계약을 못 지킨 것과 틀린 것을 한 칸에 넣으면
    형식 미준수가 오답으로 둔갑한다 — 다른 트랙에서 API 오류를 오답으로 세던
    것과 같은 종류의 결함이다.
    """

    item_id = item["id"]
    raw = answers.get(item_id)
    if raw is None:
        return {"item_id": item_id, "status": "invalid", "reason": "블록에 항목이 없다", "answer": None}
    normalized = raw.strip().lower()
    if normalized not in item["labels"]:
        return {
            "item_id": item_id, "status": "invalid",
            "reason": f"허용되지 않은 라벨: {raw!r}", "answer": raw,
        }
    return {
        "item_id": item_id,
        "status": "pass" if normalized == expected else "fail",
        "answer": normalized,
        "expected": expected,
    }


def load_run_records(run_dir: Path) -> tuple[dict[str, Any] | None, dict[str, str]]:
    """런 디렉토리에서 매니페스트와 프롬프트별 응답을 읽는다."""

    run_dir = Path(run_dir)
    manifest_path = run_dir / "run.json"
    manifest = None
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            manifest = {"status": "unreadable"}
    responses: dict[str, str] = {}
    for path in sorted(run_dir.glob("*.json")):
        if path.name == "run.json":
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(payload, dict) and "response" in payload:
            responses[path.stem] = payload
    return manifest, responses


def score_run(run_dir: Path, contract=None, answer_key=None) -> dict[str, Any]:
    """한 런의 항목별 벡터. 채점 불가면 그 사유를 들고 나온다."""

    contract = contract or load_contract()
    answer_key = answer_key or load_answer_key()
    run_dir = Path(run_dir)
    manifest, records = load_run_records(run_dir)

    blockers: list[str] = []
    if manifest is None:
        # 매니페스트가 없으면 이 산출물이 완결된 한 번의 시도인지 알 수 없다.
        blockers.append("run.json 이 없다 — 계약 이전에 만들어진 산출물이다")
    else:
        if manifest.get("status") != "complete":
            blockers.append(f"런이 완결되지 않았다 (status={manifest.get('status')!r})")
        recorded = (manifest.get("answer_contract") or {}).get("version")
        if recorded is None:
            blockers.append("계약 없이 돌린 런이다 — 구조화 채점 대상이 아니다")
        elif recorded != contract["version"]:
            blockers.append(f"계약 버전이 다르다: {recorded} vs {contract['version']}")

    items: list[dict[str, Any]] = []
    for prompt_stem in sorted((contract.get("prompts") or {})):
        defined = items_for(contract, prompt_stem)
        record = records.get(prompt_stem)
        if record is None:
            for item in defined:
                items.append({
                    "item_id": item["id"], "status": "invalid",
                    "reason": f"{prompt_stem} 응답이 없다", "answer": None,
                })
            continue
        answers = parse_answers(record["response"], contract)
        for item in defined:
            items.append(score_item(item, answers, answer_key["items"][item["id"]]["expected"]))

    return {
        "scoring_version": SCORING_VERSION,
        "contract_version": contract["version"],
        "answer_key_version": answer_key["version"],
        "session": run_dir.parents[1].name if len(run_dir.parents) > 1 else None,
        "model": (manifest or {}).get("requested_model"),
        "scorable": not blockers,
        "blockers": blockers,
        "items": items,
        # 합계는 낸다. **평균과 순위는 내지 않는다** — 5개짜리 벡터를 하나의 수로
        # 접으면 그 수는 표본 크기를 숨긴다.
        "counts": {
            status: sum(1 for entry in items if entry["status"] == status)
            for status in ("pass", "fail", "invalid")
        },
    }


def discrimination(scored_runs: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """어떤 항목이 실제로 모델을 갈랐는지.

    모든 모델이 같은 답을 낸 항목은 이 모델 집합에서 정보를 주지 않는다. 그 사실을
    함께 내지 않으면 벡터가 실제보다 넓은 것을 재는 것처럼 보인다.
    """

    by_item: dict[str, set[str]] = {}
    invalid_counts: dict[str, int] = {}
    for run in scored_runs:
        if not run.get("scorable"):
            continue
        for entry in run["items"]:
            item_id = entry["item_id"]
            by_item.setdefault(item_id, set())
            invalid_counts.setdefault(item_id, 0)
            if entry["status"] == "invalid":
                # 형식을 못 지킨 것은 **다른 답이 아니다**. invalid 를 답의 한 종류로
                # 세면 모두가 같은 답을 낸 항목이 '변별함' 으로 둔갑한다 — 이 트랙이
                # 피하려는 바로 그 혼동이다.
                invalid_counts[item_id] += 1
                continue
            by_item[item_id].add(str(entry.get("answer")))
    return {
        item_id: {
            "distinct_answers": sorted(answers),
            "discriminating": len(answers) > 1,
            "invalid_runs": invalid_counts[item_id],
        }
        for item_id, answers in sorted(by_item.items())
    }


def constant_baseline(contract=None, answer_key=None) -> dict[str, Any]:
    """항상 같은 라벨만 답하는 전략이 얻는 최대 통과 수.

    항목 수가 적으면 상수 전략이 놀랄 만큼 잘 나온다. 이 수를 옆에 두지 않으면
    통과 개수가 실력으로 읽힌다.
    """

    contract = contract or load_contract()
    answer_key = answer_key or load_answer_key()
    all_items = [item for prompt in contract["prompts"].values() for item in prompt["items"]]
    total = len(all_items)
    scores: dict[str, int] = {}
    for label in sorted({label for item in all_items for label in item["labels"]}):
        scores[label] = sum(
            1 for item in all_items
            if label in item["labels"] and answer_key["items"][item["id"]]["expected"] == label
        )
    best = max(scores.values()) if scores else 0
    return {
        "total_items": total,
        "per_label": scores,
        "best_constant_passes": best,
        "best_constant_labels": sorted(l for l, s in scores.items() if s == best),
    }
