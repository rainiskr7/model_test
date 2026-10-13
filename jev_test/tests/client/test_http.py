"""무엇: urllib 예외·시계 경계 · 입력: 가짜 연결/opener · 출력: 단일 시도 관측 · 계약 §5-5b."""

from datetime import datetime, timezone
from http.client import BadStatusLine, HTTPResponse, IncompleteRead
from io import BytesIO
from types import SimpleNamespace
from urllib.error import HTTPError, URLError
from urllib.request import AbstractHTTPHandler, HTTPHandler

import pytest

from jeveval.client import http
from jeveval.types import AttemptResult


class Response(BytesIO):
    status = 200
    headers = {"Retry-After": " 1 "}

    def __init__(self, body=b"ok", steps=None):
        super().__init__(body)
        self.steps = iter(steps) if steps is not None else None

    def read1(self, size):
        if self.steps is None:
            return super().read1(size)
        value = next(self.steps, b"")
        if isinstance(value, Exception):
            raise value
        return value


def opener_with(value):
    def open_response(request, timeout):
        assert request.get_method() == "POST" and request.data == b"{}"
        assert request.get_header("Content-type") == "application/json; charset=utf-8"
        assert timeout == .25
        if isinstance(value, Exception):
            raise value
        return value
    return SimpleNamespace(open=open_response)


@pytest.mark.parametrize("exc,expected", [
    (URLError(TimeoutError("secret")), "timeout"), (TimeoutError("secret"), "timeout"),
    (URLError(ConnectionRefusedError("secret")), "transport:ConnectionRefusedError"),
    (URLError("secret"), "transport:str"), (BadStatusLine("secret"), "transport:BadStatusLine"),
    (ConnectionResetError("secret"), "transport:ConnectionResetError")])
def test_open_failures(exc, expected):
    result = http.post("http://127.0.0.1/", b"{}", .25, opener=opener_with(exc))
    assert result.transport_error == expected
    assert result.http_status is result.retry_after is None and result.response_raw == ""
    assert "secret" not in repr(result)


@pytest.mark.parametrize("stage", ["request", "getresponse"])
def test_real_urllib_wraps_only_request_timeout(stage):
    class Connection:
        def __init__(self, *args, **kwargs):
            pass

        def set_debuglevel(self, level):
            pass

        def request(self, *args, **kwargs):
            if stage == "request":
                raise TimeoutError("synthetic")

        def getresponse(self):
            raise TimeoutError("synthetic")

        def close(self):
            pass

    def open_response(request, timeout):
        request.timeout = timeout
        return AbstractHTTPHandler().do_open(Connection, request)

    result = http.post("http://127.0.0.1/", b"{}", 1, opener=SimpleNamespace(open=open_response))
    assert result.transport_error == "timeout" and result.http_status is None


@pytest.mark.parametrize("status", [422, 503])
def test_http_error_is_a_response(status):
    error = HTTPError("http://127.0.0.1/", status, "error", {"Retry-After": "1"}, BytesIO(b"body"))
    result = http.post(error.url, b"{}", .25, opener=opener_with(error))
    assert (result.http_status, result.retry_after, result.response_raw) == (status, "1", "body")
    assert result.transport_error is None and error.closed


@pytest.mark.parametrize("exc,expected,raw", [
    (IncompleteRead(b"tail", 4), "transport:IncompleteRead", "parttail"),
    (TimeoutError(), "timeout", "part"),
    (ConnectionResetError(), "transport:ConnectionResetError", "part")])
@pytest.mark.parametrize("status", [200, 503])
def test_partial_body_preserves_status_headers_and_bytes(exc, expected, raw, status):
    response = Response(steps=[b"part", exc])
    response.status = status
    value = response if status == 200 else HTTPError(
        "http://127.0.0.1/", status, "error", response.headers, response)
    result = http.post("http://127.0.0.1/", b"{}", .25, opener=opener_with(value))
    assert (result.http_status, result.retry_after) == (status, " 1 ")
    assert (result.transport_error, result.response_raw) == (expected, raw)
    assert response.closed


def test_clock_and_json_roundtrip():
    ticks = iter([50.0, 50.125])
    dates = iter([datetime(2026, 10, 13, 1, 2, 3, 123456, timezone.utc),
                  datetime(2026, 10, 13, 1, 2, 3, 248456, timezone.utc)])
    clock = SimpleNamespace(utc_now=lambda: next(dates), monotonic=lambda: next(ticks))
    result = http.post("http://127.0.0.1/", b"{}", .25, clock, opener_with(Response(b"\xff")))
    assert result.started_at == "2026-10-13T01:02:03.123Z"
    assert result.ended_at == "2026-10-13T01:02:03.248Z" and result.latency_ms == 125.0
    assert type(result.latency_ms) is float and result.response_raw == {"b64": "/w=="}
    assert AttemptResult.from_dict(result.to_dict()) == result


def test_empty_proxy_handler_is_passed_to_real_opener(monkeypatch):
    build = http.build_opener
    captured = []

    def capture(*handlers):
        captured.extend(handlers)
        opener = build(*handlers)
        opener.open = opener_with(Response()).open
        return opener

    monkeypatch.setattr(http, "build_opener", capture)
    http.post("http://127.0.0.1/", b"{}", .25)
    proxies = [h for h in captured if isinstance(h, http.ProxyHandler)]
    assert len(proxies) == 1 and proxies[0].proxies == {}


def wire_opener(raw, calls):
    class Handler(HTTPHandler):
        def http_open(self, request):
            calls.append(request.full_url)
            sock = SimpleNamespace(makefile=lambda *args: BytesIO(raw))
            response = HTTPResponse(sock)
            response.begin()
            response.url, response.msg = request.full_url, response.reason
            return response

    return http.build_opener(http.ProxyHandler({}), Handler(), http._NoRedirect())


@pytest.mark.parametrize("code", [200, 301, 302, 303, 307, 308, 422, 503])
def test_stdlib_status_and_malformed_location_without_sockets(code):
    raw = (f"HTTP/1.1 {code} Synthetic\r\nContent-Length: 3\r\n"
           "Location: http://[\r\nRetry-After: 1\r\n\r\nabc").encode()
    calls = []
    result = http.post("http://127.0.0.1/", b"{}", 1, opener=wire_opener(raw, calls))
    assert (result.http_status, result.retry_after, result.response_raw) == (code, "1", "abc")
    assert result.transport_error is None and calls == ["http://127.0.0.1/"]


@pytest.mark.parametrize("code", [200, 503])
@pytest.mark.parametrize("framing", [b"Content-Length: 5\r\n\r\nabc",
    b"Transfer-Encoding: chunked\r\n\r\n5\r\nabc"])
def test_stdlib_partial_content_length_and_chunked_without_sockets(code, framing):
    raw = f"HTTP/1.1 {code} Synthetic\r\n".encode() + framing
    result = http.post("http://127.0.0.1/", b"{}", 1, opener=wire_opener(raw, []))
    assert (result.http_status, result.response_raw) == (code, "abc")
    assert result.transport_error == "transport:IncompleteRead"
