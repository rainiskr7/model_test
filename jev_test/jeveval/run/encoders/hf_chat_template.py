"""무엇: B1 no-think 길이 측정 · 입력: 로컬 토크나이저·CallPlan · 출력: LengthInfo · 계약 §4-3·§8-6."""

import os
from pathlib import Path

from jeveval.io.hashes import sha256_file
from jeveval.run.length import token_end
from jeveval.types import CallPlan, LengthInfo, ModelConfig


def _verified_path(cfg: ModelConfig) -> Path:
    """목록 밖 파일은 무시하고 폴더 안의 명시된 파일만 정확히 대조한다."""
    path, hashes = cfg.tokenizer.get("path"), cfg.tokenizer.get("files_sha256")
    if not isinstance(path, str) or not path or not isinstance(hashes, dict) or not hashes:
        raise ValueError("incomplete tokenizer configuration")
    root = Path(path).resolve()
    if not root.is_dir():
        raise ValueError("tokenizer path must be a directory")
    for name, expected in hashes.items():
        file = (root / name).resolve()
        if not file.is_relative_to(root) or not file.is_file():
            raise ValueError(f"tokenizer file missing or outside directory: {name}")
        if sha256_file(file) != expected:
            raise ValueError(f"tokenizer hash mismatch: {name}")
    return root


def _ids(value) -> list[int]:
    """배치·tensor·bool을 토큰 목록으로 간주하지 않는다."""
    if not isinstance(value, list) or any(type(token) is not int for token in value):
        raise ValueError("expected list[int] token IDs")
    return value


def _state_span(plan: CallPlan, text: str) -> tuple[int, int, int]:
    """trim 뒤 state 범위와 대상 끝을 반환한다.

    Jinja2 filters.do_trim은 soft_str(value).strip(chars)를 호출하며 기본 chars=None이므로
    문자열 user에는 Python str.strip()과 같은 공백 집합을 적용한다.
    """
    users = [m["content"] for m in plan.b1_call.messages if m["role"] == "user"]
    state = plan.rendered.state
    if len(users) != 1 or not isinstance(users[0], str) or not users[0].startswith(state):
        raise ValueError("expected one user message starting with state")
    user = users[0]
    if not state.strip():
        raise ValueError("state must contain non-whitespace characters")
    right_trimmed = user.rstrip()
    if right_trimmed.endswith(state) or len(right_trimmed) < len(state):
        raise ValueError("user must have a suffix keeping trailing trim outside state")
    rendered_user = user.strip()
    start = text.find(rendered_user)
    if start < 0 or text.find(rendered_user, start + 1) != -1:
        raise ValueError("user content must occur exactly once in rendered text")
    end = plan.rendered.target_end_char
    if type(end) is not int or not 0 <= end <= len(state):
        raise ValueError("target end must be inside state")
    removed = len(user) - len(user.lstrip())
    return start, start + len(state) - removed, max(0, end - removed)


def _state_offsets(offsets, text: str, start: int, end: int, count: int):
    """양의 겹침을 갖는 토큰만 state 기준으로 옮기며 경계는 임의 보정하지 않는다."""
    if len(offsets) != count:
        raise ValueError("offset count differs from token count")
    result = []
    for left, right in offsets:
        if (type(left) is not int or type(right) is not int
                or not 0 <= left <= right <= len(text)):
            raise ValueError("invalid token offsets")
        if max(left, start) < min(right, end):
            result.append((left - start, right - start))
    return result


class HfChatTemplateNoThink:
    """검증된 로컬 chat template에 thinking 비활성 규칙을 적용한다."""

    def __init__(self, cfg: ModelConfig):
        """파일 대조 후 오프라인으로만 토크나이저를 로드한다."""
        path = _verified_path(cfg)
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        from transformers import AutoTokenizer

        self.tokenizer = AutoTokenizer.from_pretrained(
            str(path), local_files_only=True, trust_remote_code=False)
        self.limit = cfg.limit["tokens"]

    def measure(self, plan: CallPlan) -> LengthInfo:
        """템플릿 ID와 재인코딩 ID가 같을 때만 문자 위치를 토큰 위치로 변환한다."""
        if plan.kind != "b1":
            raise NotImplementedError("systemone encoder requires model-specific P0")
        if self.limit is None:
            raise ValueError("limit.tokens must not be null")
        if plan.b1_call is None:
            raise ValueError("B1 call is missing")
        kwargs = dict(add_generation_prompt=True, enable_thinking=False, return_dict=False)
        ids = _ids(self.tokenizer.apply_chat_template(
            plan.b1_call.messages, tokenize=True, **kwargs))
        text = self.tokenizer.apply_chat_template(
            plan.b1_call.messages, tokenize=False, **kwargs)
        if not isinstance(text, str):
            raise ValueError("chat template must render a string")
        encoded = self.tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)
        if _ids(encoded["input_ids"]) != ids:
            raise ValueError("re-encoded token IDs differ from chat template")
        start, end, target_char = _state_span(plan, text)
        offsets = _state_offsets(encoded["offset_mapping"], text, start, end, len(ids))
        target = token_end(offsets, target_char)
        return LengthInfo(len(ids), target, self.limit, len(ids) - len(offsets))
