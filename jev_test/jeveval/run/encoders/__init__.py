"""무엇: 길이 인코더 등록 · 입력: ModelConfig · 출력: Measurer · 계약 §4-3·§8-6."""

from typing import Callable

from jeveval.run.length import Measurer
from jeveval.types import ModelConfig

from .hf_chat_template import HfChatTemplateNoThink

ENCODERS: dict[str, Callable[[ModelConfig], Measurer]] = {
    "hf_chat_template_no_think": HfChatTemplateNoThink,
}


def measurer_for(cfg: ModelConfig) -> Measurer:
    """미확정·미등록 규칙은 거부하고 등록된 측정기를 만든다."""
    rule = cfg.encoder.get("rule")
    if not isinstance(rule, str) or rule not in ENCODERS:
        raise ValueError("unknown encoder rule")
    return ENCODERS[rule](cfg)
