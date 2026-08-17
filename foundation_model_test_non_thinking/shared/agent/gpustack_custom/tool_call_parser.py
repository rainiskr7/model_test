"""Plain-text tool_call JSON 추출 유틸."""

import json
import re
import sys
import uuid
from typing import Any, Dict, List, Optional, Tuple


_TOOL_CALL_MARKER = '"tool_call"'
_TOOL_CALL_KEY_CANDIDATE = re.compile(
    r"(?<![A-Za-z0-9_])(?:['\"]tool_call['\"]|tool_call)\s*:"
)
_TEXT_CALL_PREFIX = re.compile(
    r"(?<![A-Za-z0-9_])call:([A-Za-z_][A-Za-z0-9_]*)\s*:?\s*(?=\{)"
)


def _warn_decode_failed(start: int, exc: json.JSONDecodeError) -> None:
    print(
        f"[adapter] tool_call JSON 디코드 실패: pos={start}, error={exc.msg}",
        file=sys.stderr,
    )


def _decode_covering_marker(
    decoder: json.JSONDecoder,
    content: str,
    marker_pos: int,
) -> Optional[Tuple[Dict[str, Any], int, int]]:
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
            return parsed, end, candidate

        candidate = content.rfind("{", 0, candidate)

    if last_error is not None:
        _warn_decode_failed(*last_error)
    return None


def _openai_tool_call(name: str, arguments: Any) -> Dict[str, Any]:
    return {
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


def contains_tool_call_candidate(content: str) -> bool:
    """디코드 여부와 무관하게 호출을 시도한 형태인지 저비용으로 판별한다."""
    return bool(
        _TOOL_CALL_KEY_CANDIDATE.search(content)
        or _TEXT_CALL_PREFIX.search(content)
    )


def extract_tool_calls(content: str) -> List[Dict[str, Any]]:
    """텍스트 응답에서 지원하는 tool call 형태를 JSON 디코더로 추출한다."""
    decoder = json.JSONDecoder()
    located_calls: List[Tuple[int, Dict[str, Any]]] = []
    decoded_ranges: List[Tuple[int, int]] = []
    cursor = 0

    while True:
        marker_pos = content.find(_TOOL_CALL_MARKER, cursor)
        if marker_pos == -1:
            break

        decoded = _decode_covering_marker(decoder, content, marker_pos)
        if decoded is None:
            cursor = marker_pos + len(_TOOL_CALL_MARKER)
            continue

        parsed, end, start = decoded
        decoded_ranges.append((start, end))
        cursor = max(end, marker_pos + len(_TOOL_CALL_MARKER))

        tc = parsed.get("tool_call", {})
        if not isinstance(tc, dict):
            continue

        name = tc.get("name")
        if not name:
            continue

        arguments = tc.get("arguments", {})
        located_calls.append((marker_pos, _openai_tool_call(name, arguments)))

    # Gemma 계열 plain-text 형태:
    #   call:Tool:{...}  /  call:Tool{...}
    # 이름은 ASCII identifier 로 제한하고 바로 뒤 JSON 객체를 arguments 로 쓴다.
    for match in _TEXT_CALL_PREFIX.finditer(content):
        if any(start <= match.start() < end for start, end in decoded_ranges):
            continue

        arguments_start = match.end()
        try:
            arguments, _ = decoder.raw_decode(content, arguments_start)
        except json.JSONDecodeError as exc:
            _warn_decode_failed(arguments_start, exc)
            continue

        if not isinstance(arguments, dict):
            continue

        located_calls.append(
            (match.start(), _openai_tool_call(match.group(1), arguments))
        )

    located_calls.sort(key=lambda item: item[0])
    return [call for _, call in located_calls]
