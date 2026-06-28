"""thinking 모델 출력(추론 트레이스) 분리 — nlu 트랙 전용 모듈.

nlu 러너는 openai SDK 가 아니라 raw requests 로 호출하므로 dict 응답을 다룬다.
로직은 multimodal/benches/reasoning.py 와 동일하지만, 본 repo 의 트랙 self-contained
원칙(CONVENTIONS §1)에 따라 트랙별로 둔다.
"""

import re
from typing import Optional, Tuple

_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_THINK_INNER_RE = re.compile(r"<think>(.*?)</think>", re.DOTALL | re.IGNORECASE)
_THINK_OPEN_RE = re.compile(r"<think>", re.IGNORECASE)
_THINK_CLOSE_RE = re.compile(r"</think>", re.IGNORECASE)


def split_reasoning(
    content: Optional[str], reasoning_content: Optional[str] = None
) -> Tuple[str, Optional[str]]:
    """(final_answer, reasoning) 반환. multimodal 모듈과 동일 의미.

    - reasoning_content 가 있으면 추론으로 채택.
    - content 의 <think>...</think> 제거 후 최종 답 반환(닫힘/열림 케이스 처리).
    """
    content = content or ""
    inline_parts = _THINK_INNER_RE.findall(content)
    cleaned = _THINK_BLOCK_RE.sub("", content)
    if _THINK_CLOSE_RE.search(cleaned):
        cleaned = _THINK_CLOSE_RE.split(cleaned)[-1]
    elif _THINK_OPEN_RE.search(cleaned):
        # 닫는 </think> 없이 잘린 경우: <think> 뒤를 남겨 답을 회수.
        cleaned = _THINK_OPEN_RE.split(cleaned)[-1]
    reasoning = reasoning_content or ("\n".join(inline_parts) if inline_parts else None)
    return cleaned.strip(), reasoning


def split_from_message(message: dict) -> Tuple[str, Optional[str]]:
    """OpenAI-compat 응답 message dict 에서 (final_answer, reasoning) 추출.

    추론 필드 키는 서버마다 'reasoning_content'(표준) 또는 'reasoning'(일부 빌드, 실측).
    """
    content = message.get("content") or ""
    reasoning = message.get("reasoning_content") or message.get("reasoning")
    return split_reasoning(content, reasoning)
