"""무엇: 목록·B1 설정 읽기 · 입력: 경로 · 출력: 목록/B1Config · 계약 §1-1·§6-2."""

import json
from pathlib import Path
from typing import Any

from jeveval.contract.b1_prompt import check_user_template
from jeveval.io.config import read_yaml
from jeveval.types import B1Config


def _unique_object(pairs):
    """중첩 JSON 객체의 중복 키도 거부한다."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_lists(directory) -> dict[str, Any]:
    """파일 이름순으로 읽되 JSON 내부 목록·객체 순서는 유지한다."""
    return {path.stem: json.loads(path.read_text(encoding="utf-8"),
                                  object_pairs_hook=_unique_object)
            for path in sorted(Path(directory).glob("*.json"))}


def read_b1_config(path) -> B1Config:
    """닫힌 네 키와 필드 타입·사용자 문구 틀을 검사한다."""
    data = read_yaml(path)
    if not isinstance(data, dict) or set(data) != {"system", "user_template", "labels", "params"}:
        raise ValueError("B1 config requires exactly system, user_template, labels, params")
    errors = check_user_template(data["user_template"])
    if errors:
        raise ValueError("; ".join(errors))
    try:
        return B1Config.from_dict(data)
    except TypeError as exc:
        raise ValueError("invalid B1 config field type") from exc
