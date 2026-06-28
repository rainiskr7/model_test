"""OpenAI-compatible API 클라이언트 + 이미지 처리 — 단일 책임 모듈.

make_client / image_to_data_url / chat_with_image (thinking 추론 분리 포함).
common.py 가 re-export 하므로 기존 `from common import ...` 도 그대로 동작.
"""

import io
import os
import time
import base64
from typing import Optional, Any

try:
    from openai import OpenAI
except ImportError as e:
    raise SystemExit("openai 패키지 미설치 — `uv pip install openai pillow datasets`") from e

# thinking 모델 출력(추론 트레이스) 분리는 전용 모듈에 위임 (단일 책임).
from reasoning import split_reasoning, message_content_and_reasoning


def make_client(base_url: str, api_key: Optional[str] = None) -> OpenAI:
    """OpenAI-compat 클라이언트 생성.

    base_url 정규화: 사용자가 /chat/completions 까지 입력해도 자동 제거.
    OpenAI SDK 는 base_url 을 /v1 까지로 받고 /chat/completions 자동 추가하므로,
    중복 path 방지 위해 normalize.
    """
    api_key = api_key or os.environ.get("OPENAI_API_KEY") or "EMPTY"
    base_url = base_url.rstrip("/")
    if base_url.endswith("/chat/completions"):
        base_url = base_url[: -len("/chat/completions")]
    if base_url.endswith("/completions"):
        base_url = base_url[: -len("/completions")]
    return OpenAI(base_url=base_url, api_key=api_key)


def image_to_data_url(img: Any, fmt: str = "PNG") -> str:
    """PIL Image → data URL (base64-encoded)."""
    buf = io.BytesIO()
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    img.save(buf, format=fmt)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/{fmt.lower()};base64,{b64}"


def _is_retriable(exc: Exception) -> bool:
    """429 / 5xx / timeout / connection error 만 재시도. 4xx (auth, malformed) 은 즉시 실패."""
    msg = str(exc).lower()
    name = type(exc).__name__.lower()
    # 명시적 재시도 대상
    if any(k in name for k in ("timeout", "connection", "ratelimit")):
        return True
    if any(k in msg for k in ("timeout", "rate limit", "rate_limit", "429", "500", "502", "503", "504", "connection")):
        return True
    # 명시적 비-재시도 (인증/요청 오류)
    if any(k in msg for k in ("401", "403", "404", "400", "invalid", "unauthorized")):
        return False
    # 기본은 재시도 안 함 (안전)
    return False


def chat_with_image(
    client: OpenAI,
    model: str,
    prompt: str,
    image: Any,
    max_tokens: int = 2048,
    temperature: float = 0.6,
    top_p: Optional[float] = 0.95,
    top_k: Optional[int] = 20,
    seed: Optional[int] = 42,
    timeout: Optional[float] = 600.0,
    retry_max: int = 3,
    retry_backoff: float = 1.0,
    return_reasoning: bool = False,
) -> Any:
    """Send single text+image prompt, return think-stripped 최종 답.

    thinking 모델 대응: 응답에서 추론(reasoning_content / <think>...</think>)을 분리하고
    최종 답 텍스트만 반환한다. return_reasoning=True 면 (answer, reasoning) tuple.

    재현성·견고성:
    - sampling 기본값은 thinking 권장값(temp 0.6 / top_p 0.95 / top_k 20) + 고정 seed.
      greedy(temp 0)는 Qwen thinking 모드에서 반복·퇴화를 유발하므로 비권장.
      top_k 는 OpenAI 표준이 아니라 vLLM extra_body 로 전달.
    - seed: OpenAI seed 파라미터 (서버 지원 시 결정론적). 미설정 시 미전달.
    - 재시도 정책: 429/5xx/timeout/connection 만 지수 backoff + jitter (±20%).
      4xx (auth, invalid) 은 즉시 실패 — 재시도 무의미.
    - retry_max: 재시도 횟수 (default 3)

    실패 시 마지막 Exception raise.
    """
    import random
    data_url = image_to_data_url(image)
    messages = [{
        "role": "user",
        "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": data_url}},
        ],
    }]
    kwargs = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if top_p is not None:
        kwargs["top_p"] = top_p
    if top_k is not None and top_k > 0:
        # top_k 는 OpenAI 표준 파라미터가 아님 → vLLM extra_body 로 전달
        kwargs["extra_body"] = {"top_k": top_k}
    if seed is not None:
        kwargs["seed"] = seed
    if timeout is not None:
        kwargs["timeout"] = timeout

    for attempt in range(retry_max):
        try:
            resp = client.chat.completions.create(**kwargs)
            content, reasoning = message_content_and_reasoning(resp.choices[0].message)
            answer, reasoning = split_reasoning(content, reasoning)
            return (answer, reasoning) if return_reasoning else answer
        except Exception as e:
            if attempt < retry_max - 1 and _is_retriable(e):
                # 지수 backoff + jitter (±20%)
                wait = retry_backoff * (2 ** attempt)
                wait *= (0.8 + 0.4 * random.random())
                time.sleep(wait)
            else:
                raise
