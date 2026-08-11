"""서빙 백엔드별 요청 제약 적용 — diffusion 모델 등 비표준 백엔드 대응.

배경
----
vLLM 의 diffusion 백엔드(DiffusionGemma 등)는 일반 autoregressive 모델과
요청 규약이 다르다. 평가 트랙은 모델마다 코드를 갈아끼우는 대신 이 모듈을
통해 payload 를 한 번 통과시킨다.

적용되는 제약 3종:

1. 미지원 sampling 파라미터 제거
   diffusion 백엔드는 아래 파라미터를 400 으로 거부한다.
     temperature, min_p, seed, min_tokens, logit_bias, bad_words,
     allowed_token_ids
   평가 코드는 결정론성 확보용으로 temperature=0 을 항상 보내므로,
   제거하지 않으면 단 한 건도 통과하지 못한다.

2. skip_special_tokens=False 강제
   Gemma4 계열 파서는 `<|channel>` / `<|turn>` 등 special token 경계를 보고
   reasoning 과 content 를 분리한다. 그런데 비스트리밍 경로는 파서가
   *디토크나이즈된 문자열*을 받으므로, skip_special_tokens=True(기본값)면
   경계 토큰이 이미 지워진 뒤라 파서가 아무것도 못 찾고
   content=None, reasoning=None 을 반환한다 (토큰은 정상 생성됨).
   실측: max_tokens=2048 요청에서 265 토큰 생성 후 두 필드 모두 None
        → skip_special_tokens=False 로 바꾸니 426 자 정상 반환.

3. max_tokens 상한 (선택)
   서버의 --max-model-len 이 작으면 prompt + max_tokens 가 이를 넘겨 400 이
   난다. nlu 는 max_tokens=8192 고정인데 --max-model-len 8192 서버에서는
   프롬프트 길이와 무관하게 항상 실패한다. 서버를 더 큰 max-model-len 으로
   재서빙하는 것이 정석이나, 그게 불가할 때 클라이언트에서 상한을 건다.

설정은 모델 yaml 의 `serving:` 섹션 → load_model_config.py 가 env 로 export
→ 이 모듈이 env 를 읽는다. env 미설정 시 모든 함수는 no-op 이므로
기존 autoregressive 모델 경로는 바이트 단위로 동일하게 동작한다.
"""

from __future__ import annotations

import os
from typing import Any, MutableMapping

__all__ = [
    "unsupported_sampling_params",
    "max_output_tokens",
    "force_skip_special_tokens",
    "apply",
]

ENV_UNSUPPORTED = "SERVING_UNSUPPORTED_SAMPLING_PARAMS"
ENV_MAX_OUTPUT = "SERVING_MAX_OUTPUT_TOKENS"
ENV_SKIP_SPECIAL = "SERVING_FORCE_SKIP_SPECIAL_TOKENS"


def unsupported_sampling_params() -> frozenset[str]:
    """제거 대상 파라미터 이름 집합. 미설정 시 빈 집합."""
    raw = os.environ.get(ENV_UNSUPPORTED, "")
    return frozenset(p.strip() for p in raw.split(",") if p.strip())


def max_output_tokens() -> int | None:
    """max_tokens 상한. 미설정/파싱 불가 시 None (상한 없음)."""
    raw = os.environ.get(ENV_MAX_OUTPUT, "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if value > 0 else None


def force_skip_special_tokens() -> bool | None:
    """skip_special_tokens 강제값. 미설정 시 None (건드리지 않음)."""
    raw = os.environ.get(ENV_SKIP_SPECIAL, "").strip().lower()
    if raw in ("false", "0", "no"):
        return False
    if raw in ("true", "1", "yes"):
        return True
    return None


def apply(payload: MutableMapping[str, Any], *, sdk: bool = False) -> MutableMapping[str, Any]:
    """제약을 payload 에 in-place 적용하고 같은 객체를 반환.

    env 가 하나도 설정되지 않았으면 payload 는 전혀 변경되지 않는다.

    sdk
        True 면 openai 파이썬 SDK 호출용으로 취급한다.
        ``skip_special_tokens`` 는 OpenAI 표준 파라미터가 아니라서
        ``client.chat.completions.create(**payload)`` 에 top-level 로 넣으면
        TypeError 가 난다. SDK 모드에서는 ``extra_body`` 안으로 넣는다.
        raw HTTP(requests) 호출부는 sdk=False (기본값) 로 top-level 에 둔다.
    """
    for name in unsupported_sampling_params():
        payload.pop(name, None)
        if sdk:
            extra = payload.get("extra_body")
            if isinstance(extra, MutableMapping):
                extra.pop(name, None)

    cap = max_output_tokens()
    if cap is not None:
        current = payload.get("max_tokens")
        if isinstance(current, int) and current > cap:
            payload["max_tokens"] = cap

    skip = force_skip_special_tokens()
    if skip is not None:
        if sdk:
            extra = payload.get("extra_body")
            if not isinstance(extra, MutableMapping):
                extra = {}
                payload["extra_body"] = extra
            extra["skip_special_tokens"] = skip
        else:
            payload["skip_special_tokens"] = skip

    return payload
