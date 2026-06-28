"""thinking 모델 출력(추론 트레이스) 분리 — agent 트랙 전용 모듈.

agent 어댑터는 openai SDK 응답 객체를 다루며, tool-call 을 plain-text content 에서
정규식으로 추출한다. 추론 트레이스 안에 tool_call 모양 JSON 이 들어 있으면 잘못된
tool call 로 오인될 수 있으므로, content 는 *추론을 strip 한* 텍스트만 쓰고 추론은
reasoning_content 로 따로 보존한다.

로직은 다른 트랙의 reasoning 모듈과 동일(트랙 self-contained, CONVENTIONS §1).
"""

import re
from typing import Any, Optional, Tuple

_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_THINK_INNER_RE = re.compile(r"<think>(.*?)</think>", re.DOTALL | re.IGNORECASE)
_THINK_OPEN_RE = re.compile(r"<think>", re.IGNORECASE)
_THINK_CLOSE_RE = re.compile(r"</think>", re.IGNORECASE)


def split_reasoning(
    content: Optional[str], reasoning_content: Optional[str] = None
) -> Tuple[str, Optional[str]]:
    """(final_content, reasoning) 반환. content 의 <think>...</think> 제거."""
    content = content or ""
    inline_parts = _THINK_INNER_RE.findall(content)
    cleaned = _THINK_BLOCK_RE.sub("", content)
    if _THINK_CLOSE_RE.search(cleaned):
        cleaned = _THINK_CLOSE_RE.split(cleaned)[-1]
    elif _THINK_OPEN_RE.search(cleaned):
        # 닫는 </think> 없이 잘린 경우: <think> 뒤를 남겨 답/tool_call 을 회수.
        cleaned = _THINK_OPEN_RE.split(cleaned)[-1]
    reasoning = reasoning_content or ("\n".join(inline_parts) if inline_parts else None)
    return cleaned.strip(), reasoning


def message_content_and_reasoning(message: Any) -> Tuple[str, Optional[str]]:
    """openai-compat message 객체에서 (content, reasoning) 추출.

    추론 필드 키가 서버마다 다름: 'reasoning_content'(vLLM 표준) 또는 'reasoning'
    (일부 gpustack/vLLM 빌드 — 실측). attribute / model_extra 양쪽에서 둘 다 확인.
    """
    content = getattr(message, "content", None) or ""
    reasoning = getattr(message, "reasoning_content", None) or getattr(message, "reasoning", None)
    if reasoning is None:
        extra = getattr(message, "model_extra", None)
        if isinstance(extra, dict):
            reasoning = extra.get("reasoning_content") or extra.get("reasoning")
    return content, reasoning
