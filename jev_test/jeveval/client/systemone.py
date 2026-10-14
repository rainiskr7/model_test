"""무엇: systemone 단일 요청 · 입력: base URL·Request · 출력: 해시·AttemptResult · 계약 §2-1·§5-5b."""

import hashlib

from jeveval.contract.request import request_bytes
from jeveval.types import AttemptResult, Request
from . import http


def systemone_url(base_url: str) -> str:
    return base_url.rstrip("/") + "/v1/systemone"


def send_systemone(base_url: str, request: Request, timeout=600,
                   post=http.post, headers: dict[str, str] | None = None) -> tuple[str, AttemptResult]:
    body = request_bytes(request)
    options = {} if headers is None else {"headers": headers}
    return hashlib.sha256(body).hexdigest(), post(systemone_url(base_url), body, timeout, **options)


def send_t0(base_url, request, timeout=600, post=http.post, headers=None):
    """T0에서 확정한 score 포함 봉투 바이트를 다시 직렬화하지 않고 한 번 보낸다 (§8-7)."""
    body = request.envelope_bytes
    return hashlib.sha256(body).hexdigest(), post(systemone_url(base_url), body, timeout, headers=headers)
