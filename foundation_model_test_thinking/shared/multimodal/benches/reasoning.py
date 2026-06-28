"""thinking/reasoning 모델 출력 처리 — 단일 책임 모듈.

thinking 모델은 최종 답 앞에 긴 추론 트레이스를 낸다. 두 형태 모두 견고하게 처리:
  (a) 서버가 --reasoning-parser 로 분리 → message.reasoning_content 에 추론,
      message.content 엔 최종 답만.
  (b) 분리 없음 → content 안에 <think>...</think> 인라인.

평가/파싱은 항상 '최종 답'만 봐야 하므로, 추론을 떼어낸 clean content 를 돌려준다.
이 로직은 multimodal·nlu·agent·kreta 가 공통으로 필요로 하지만, 본 repo 는
트랙별 self-contained 를 원칙으로 하므로 (CONVENTIONS §1) 각 트랙에 동일 모듈을 둔다.
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
    """(final_answer, reasoning) 반환.

    - reasoning_content (서버 --reasoning-parser 분리분) 가 있으면 추론으로 채택.
    - content 의 인라인 <think>...</think> 는 제거하고 남은 텍스트를 최종 답으로:
      · 닫는 </think> 가 있으면 '마지막 </think> 뒤'만 최종 답으로 (중간 think 흔적 제거).
      · 열린 <think> 만 있고 닫힘 없음(생성 잘림 등) → '<think> 뒤' 텍스트를 남겨
        말미의 답 마커를 회수 (그 앞은 보통 빈 문자열).
    """
    content = content or ""
    inline_parts = _THINK_INNER_RE.findall(content)  # 태그 제외 내부 텍스트만 보존
    cleaned = _THINK_BLOCK_RE.sub("", content)
    if _THINK_CLOSE_RE.search(cleaned):
        cleaned = _THINK_CLOSE_RE.split(cleaned)[-1]
    elif _THINK_OPEN_RE.search(cleaned):
        # 닫는 </think> 없이 잘린 경우: <think> 뒤(추론 말미에 답이 있을 수 있음)를 남겨
        # 마커 추출(extract_choice/extract_final_answer 의 마지막 매치)이 답을 회수하게 한다.
        cleaned = _THINK_OPEN_RE.split(cleaned)[-1]
    reasoning = reasoning_content or ("\n".join(inline_parts) if inline_parts else None)
    return cleaned.strip(), reasoning


def message_content_and_reasoning(message: Any) -> Tuple[str, Optional[str]]:
    """OpenAI-compat message 객체에서 (content, reasoning) 추출.

    추론 필드는 서버/빌드마다 키가 다르다(비표준):
      - vLLM 표준: 'reasoning_content'
      - 일부 gpustack/vLLM 빌드: 'reasoning'  ← 실측(qwen3.5_35b-thinking)
    attribute / model_extra 양쪽에서 두 키를 모두 확인한다.
    """
    content = getattr(message, "content", None) or ""
    reasoning = getattr(message, "reasoning_content", None) or getattr(message, "reasoning", None)
    if reasoning is None:
        extra = getattr(message, "model_extra", None)
        if isinstance(extra, dict):
            reasoning = extra.get("reasoning_content") or extra.get("reasoning")
    return content, reasoning


def strip_reasoning(content: Optional[str], reasoning_content: Optional[str] = None) -> str:
    """split_reasoning 의 답만 필요한 호출자용 단축 함수."""
    answer, _ = split_reasoning(content, reasoning_content)
    return answer
