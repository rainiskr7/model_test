"""Plain-text tool_call JSON 추출 유틸."""

import json
import sys
import uuid
from typing import Any, Dict, List, Optional, Tuple


_TOOL_CALL_MARKER = '"tool_call"'


def _warn_decode_failed(start: int, exc: json.JSONDecodeError) -> None:
    print(
        f"[adapter] tool_call JSON 디코드 실패: pos={start}, error={exc.msg}",
        file=sys.stderr,
    )


def _decode_covering_marker(
    decoder: json.JSONDecoder,
    content: str,
    marker_pos: int,
) -> Optional[Tuple[Dict[str, Any], int]]:
    last_error: Optional[Tuple[int, json.JSONDecodeError]] = None
    candidate = content.rfind("{", 0, marker_pos)

    while candidate != -1:
        try:
            parsed, end = decoder.raw_decode(content, candidate)
        except json.JSONDecodeError as exc:
            last_error = (candidate, exc)
            candidate = content.rfind("{", 0, candidate)
            continue

        if candidate <= marker_pos < end and isinstance(parsed, dict):
            return parsed, end

        candidate = content.rfind("{", 0, candidate)

    if last_error is not None:
        _warn_decode_failed(*last_error)
    return None


def extract_tool_calls(content: str) -> List[Dict[str, Any]]:
    """텍스트 응답에서 tool_call 객체를 brace-balanced 방식으로 추출한다."""
    decoder = json.JSONDecoder()
    tool_calls: List[Dict[str, Any]] = []
    cursor = 0

    while True:
        marker_pos = content.find(_TOOL_CALL_MARKER, cursor)
        if marker_pos == -1:
            break

        decoded = _decode_covering_marker(decoder, content, marker_pos)
        if decoded is None:
            cursor = marker_pos + len(_TOOL_CALL_MARKER)
            continue

        parsed, end = decoded
        cursor = max(end, marker_pos + len(_TOOL_CALL_MARKER))

        tc = parsed.get("tool_call", {})
        if not isinstance(tc, dict):
            continue

        name = tc.get("name")
        if not name:
            continue

        arguments = tc.get("arguments", {})
        tool_calls.append(
            {
                "id": f"call_{uuid.uuid4().hex[:24]}",
                "type": "function",
                "function": {
                    "name": name,
                    "arguments": (
                        json.dumps(arguments, ensure_ascii=False)
                        if isinstance(arguments, dict)
                        else str(arguments)
                    ),
                },
            }
        )

    return tool_calls
