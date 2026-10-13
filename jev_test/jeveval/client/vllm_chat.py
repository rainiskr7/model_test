"""무엇: B1 chat 전송 · 입력: B1Call·토큰 대응/본문 · 출력: 본문·바이트·시도 · 계약 §2-5·§5-5b."""

from copy import deepcopy
import hashlib
import json

from jeveval.types import AttemptResult, B1Call
from . import http


def chat_body(call: B1Call, served_name: str, label_token_ids: dict[str, int]) -> dict:
    """라벨 순서대로 토큰을 넣고 봉투 덮어쓰기·누락·토큰 충돌을 거부한다."""
    if {"model", "messages", "allowed_token_ids"} & call.params.keys():
        raise ValueError("reserved chat parameter")
    if any(label not in label_token_ids for label in call.label_order):
        raise ValueError("missing label token ID")
    ids = [label_token_ids[label] for label in call.label_order]
    if any(type(token) is not int for token in ids):
        raise ValueError("expected integer label token IDs")
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate label token IDs")
    return deepcopy({"model": served_name, "messages": call.messages, **call.params,
                     "allowed_token_ids": ids})


def chat_bytes(body: dict) -> bytes:
    return json.dumps(body, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def send_chat(base_url: str, body: dict, timeout=600,
              post=http.post) -> tuple[str, AttemptResult]:
    payload = chat_bytes(body)
    url = base_url.rstrip("/") + "/v1/chat/completions"
    return hashlib.sha256(payload).hexdigest(), post(url, payload, timeout)
