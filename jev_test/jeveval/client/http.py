"""무엇: HTTP 한 번 전송 · 입력: URL·바이트·소켓 timeout · 출력: AttemptResult · 계약 §5-5b."""

import base64
from datetime import datetime, timezone
from http.client import HTTPException, IncompleteRead
import time
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from jeveval.types import AttemptResult


class _Clock:
    """주입 시 utc_now는 aware datetime, monotonic은 초 단위 수를 돌려준다."""

    def utc_now(self):
        return datetime.now(timezone.utc)

    def monotonic(self):
        return time.monotonic()


class _NoRedirect(HTTPRedirectHandler):
    def http_error_302(self, req, fp, code, msg, headers):
        # Location 파싱조차 하지 않고 원 응답을 반환한다.
        return fp

    http_error_301 = http_error_303 = http_error_307 = http_error_308 = http_error_302


def _error(exc):
    if isinstance(exc, URLError):
        exc = exc.reason
    return "timeout" if isinstance(exc, TimeoutError) else f"transport:{type(exc).__name__}"


def _raw(body):
    try:
        return body.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return {"b64": base64.b64encode(body).decode("ascii")}


def _read_body(response):
    """read1로 이미 받은 조각을 보존하며, Content-Length보다 짧은 EOF도 오류로 둔다."""
    stream = response.fp if isinstance(response, HTTPError) else response
    read = getattr(stream, "read1", stream.read)
    chunks = []
    try:
        while True:
            chunk = read(65536)
            if not chunk:
                if getattr(stream, "length", None):
                    raise IncompleteRead(b"", stream.length)
                break
            chunks.append(chunk)
    except (OSError, HTTPException) as exc:
        if isinstance(exc, IncompleteRead):
            chunks.append(exc.partial)
        return _raw(b"".join(chunks)), _error(exc)
    return _raw(b"".join(chunks)), None


def _stamp(clock):
    return clock.utc_now().astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def post(url: str, body: bytes, timeout: float, clock=None, opener=None) -> AttemptResult:
    """재시도 없이 보낸다. timeout은 소켓 단위이며 총 소요 시간 상한은 아니다."""
    clock = clock if clock is not None else _Clock()
    opener = opener if opener is not None else build_opener(ProxyHandler({}), _NoRedirect())
    request = Request(url, data=body, method="POST",
                      headers={"Content-Type": "application/json; charset=utf-8"})
    started_at, start = _stamp(clock), clock.monotonic()
    status, retry_after, error, raw = None, None, None, ""
    try:
        try:
            response = opener.open(request, timeout=timeout)
        except HTTPError as exc:
            response = exc
        with response:
            status = response.status
            retry_after = response.headers.get("Retry-After")
            raw, error = _read_body(response)
    except (OSError, HTTPException) as exc:
        error = _error(exc)
    elapsed = float((clock.monotonic() - start) * 1000)
    return AttemptResult(started_at, _stamp(clock), elapsed, status, retry_after, error, raw)
