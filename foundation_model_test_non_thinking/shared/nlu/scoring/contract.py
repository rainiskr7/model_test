"""응답 형식 계약 — 프롬프트 본문을 건드리지 않고 뒤에 덧붙인다.

프롬프트 두 개는 자유형식이라 지금까지 비교가 전부 수작업이었다. 본문을 고치면
이미 커밋된 산출물과 비교할 수 없게 되므로, 본문은 바이트 그대로 두고 요청
시점에 계약 블록만 덧붙인다. 산출물에 계약 버전과 SHA-256 이 남으므로 계약이
있는 런과 없는 런은 섞이지 않는다.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

NLU_DIR = Path(__file__).resolve().parent.parent
CONTRACT_PATH = NLU_DIR / "contract.json"
# 모델이 라벨에 붙이는 장식: 굵게, 코드, 따옴표, 마침표, 목록 기호.
DECORATION = " \t`*.\"'-—·"
ANSWER_KEY_PATH = NLU_DIR / "answer_key.json"


def load_contract(path: Path | None = None) -> dict[str, Any]:
    return json.loads(Path(path or CONTRACT_PATH).read_text(encoding="utf-8"))


def load_answer_key(path: Path | None = None) -> dict[str, Any]:
    return json.loads(Path(path or ANSWER_KEY_PATH).read_text(encoding="utf-8"))


def items_for(contract: dict[str, Any], prompt_stem: str) -> list[dict[str, Any]]:
    """이 프롬프트가 채점하는 항목들. 계약에 없는 프롬프트면 빈 목록."""

    return list((contract.get("prompts") or {}).get(prompt_stem, {}).get("items") or [])


def render(contract: dict[str, Any], prompt_stem: str) -> str:
    """덧붙일 계약 문구. 계약에 없는 프롬프트면 빈 문자열."""

    items = items_for(contract, prompt_stem)
    if not items:
        return ""
    lines = [contract["instruction_header"], contract["block_open"]]
    for item in items:
        lines.append(f"{item['id']}: {' | '.join(item['labels'])}    # {item['gloss']}")
    lines.append(contract["block_close"])
    return "\n".join(lines)


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_answers(response: str, contract: dict[str, Any]) -> dict[str, str]:
    """응답 끝의 [ANSWER] 블록에서 항목별 라벨을 뽑는다.

    블록이 여러 번 나오면 **마지막 것**을 쓴다. 모델이 계약 문구를 되풀이한 뒤
    실제 답을 적는 경우가 있는데, 첫 블록을 집으면 라벨 목록 자체를 답으로
    읽게 된다.
    """

    open_tag = contract["block_open"]
    close_tag = contract["block_close"]
    if open_tag not in response:
        return {}
    body = response.rsplit(open_tag, 1)[1]
    body = body.split(close_tag, 1)[0]

    answers: dict[str, str] = {}
    for line in body.splitlines():
        line = line.split("#", 1)[0].strip().strip("*").strip()
        if not line or ":" not in line:
            continue
        item_id, _, value = line.partition(":")
        # 장식 문자를 한 번에 벗긴다. 순서대로 하나씩 벗기면 `drive`. 처럼 섞여
        # 있을 때 안쪽 문자가 남는다.
        item_id = item_id.strip(DECORATION)
        value = value.strip(DECORATION)
        if not item_id or not value:
            continue
        # 라벨 목록을 그대로 되돌려준 줄("walk | drive | depends")은 답이 아니다.
        if "|" in value:
            continue
        answers[item_id] = value
    return answers
