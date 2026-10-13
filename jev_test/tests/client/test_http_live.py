"""무엇: loopback HTTP 통합 · 입력: 합성 서버/가짜 proxy · 출력: 바이트·오류·무재시도 · 계약 §5-5b."""

import errno
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import socket
from threading import Thread
import time

import pytest

from jeveval.client.http import post


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        self.server.calls.append((self.path, body, self.headers["Content-Type"]))
        self.server.authorizations.append(self.headers.get("Authorization"))
        if self.path == "/disconnect":
            self.connection.shutdown(socket.SHUT_RDWR)
            self.close_connection = True
            return
        if self.path == "/delay":
            time.sleep(.15)
        code = int(self.path[1:]) if self.path[1:].isdigit() else 200
        payload = b"\xff" if self.path == "/binary" else b'  {"answer": 1}\n'
        partial = self.path in ("/partial", "/body_timeout", "/chunk_partial")
        if partial:
            payload = b"abc"
        self.send_response(code)
        self.send_header("Retry-After", "1")
        self.send_header("Connection", "close")
        if 300 <= code < 400:
            self.send_header("Location", "/echo")
        if self.path == "/chunk_partial":
            self.send_header("Transfer-Encoding", "chunked")
            payload = b"5\r\nabc"
        else:
            self.send_header("Content-Length", str(9 if partial else len(payload)))
        try:
            self.end_headers()
            self.wfile.write(payload)
            self.wfile.flush()
            if self.path == "/body_timeout":
                time.sleep(.15)
        except (BrokenPipeError, ConnectionResetError):
            pass
        self.close_connection = True


@pytest.fixture
def servers():
    running = []

    def start():
        try:
            server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        except OSError as exc:
            if exc.errno in (errno.EACCES, errno.EPERM):
                pytest.skip("loopback bind blocked")
            raise
        server.calls = []
        server.authorizations = []
        thread = Thread(target=server.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
        thread.start()
        running.append((server, thread))
        return server, f"http://127.0.0.1:{server.server_port}"

    yield start
    for server, thread in running:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.mark.parametrize("code", [200, 422, 503, 529, 201, 301, 302, 303, 307, 308])
def test_status_body_request_and_no_redirect(servers, code):
    server, url = servers()
    body = '{"state":"그대로"}'.encode()
    result = post(url + f"/{code}", body, 1)
    assert result.http_status == code and result.transport_error is None
    assert result.retry_after == "1" and result.response_raw == '  {"answer": 1}\n'
    assert server.calls == [(f"/{code}", body, "application/json; charset=utf-8")]


@pytest.mark.parametrize("path,error,raw", [
    ("/disconnect", "transport:RemoteDisconnected", ""), ("/delay", "timeout", ""),
    ("/partial", "transport:IncompleteRead", "abc"),
    ("/body_timeout", "timeout", "abc"), ("/chunk_partial", "transport:IncompleteRead", "abc")])
def test_transport_and_partial_body(servers, path, error, raw):
    server, url = servers()
    result = post(url + path, b"{}", .05)
    assert result.transport_error == error and result.response_raw == raw
    assert result.http_status == (200 if path in ("/partial", "/body_timeout", "/chunk_partial") else None)
    assert len(server.calls) == 1


def test_utf8_failure(servers):
    _, url = servers()
    assert post(url + "/binary", b"{}", 1).response_raw == {"b64": "/w=="}


def test_environment_proxy_is_never_contacted(servers, monkeypatch):
    target, url = servers()
    proxy, proxy_url = servers()
    for key in ("http_proxy", "HTTP_PROXY"):
        monkeypatch.setenv(key, proxy_url)
    for key in ("no_proxy", "NO_PROXY"):
        monkeypatch.setenv(key, "")
    result = post(url + "/echo", b"{}", 1)
    assert result.http_status == 200 and len(target.calls) == 1
    assert proxy.calls == []


def test_authorization_sent_but_not_recorded(servers):
    server, url = servers()
    secret = "Bearer synthetic-secret"
    result = post(url + "/echo", b"{}", 1, headers={"Authorization": secret})
    assert result.http_status == 200
    assert server.authorizations == [secret]
    assert secret not in repr(result) and secret not in repr(result.to_dict())
