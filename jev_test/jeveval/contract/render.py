"""무엇: state 렌더링 · 입력: 원 필드·state 설정 · 출력: Rendered · 계약 §2-2."""

import json

from jeveval.types import Rendered


def _encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def render_state(state_fields: dict | str, state_spec: dict) -> Rendered:
    """plain_text는 앞뒤 공백을 지우고, JSON은 키 순서·값을 보존해 대상 끝을 구한다."""
    if state_spec["kind"] == "plain_text":
        if not isinstance(state_fields, str):
            raise ValueError("plain_text requires a string")
        state = state_fields.strip()
        if not state:
            raise ValueError("plain_text requires non-whitespace content")
        return Rendered(state, len(state))
    if state_spec["kind"] != "json_string" or not isinstance(state_fields, dict):
        raise ValueError("json_string requires an object")
    keys = state_spec["keys"]
    if len(set(keys)) != len(keys):
        raise ValueError("duplicate state keys")
    if set(keys) != set(state_fields):
        raise ValueError("state fields must match keys")
    target = state_spec["target_key"]
    if target not in keys:
        raise ValueError("target_key must belong to keys")
    parts, target_end = [], None
    for key in keys:
        value = state_fields[key]
        encoded = _encode(value)
        parts.append(_encode(key) + ":" + encoded)
        if key == target:
            if not isinstance(value, (str, list)) or value == []:
                raise ValueError("target must be a string or nonempty list")
            target_end = len("{" + ",".join(parts)) - isinstance(value, list)
    return Rendered("{" + ",".join(parts) + "}", target_end)
