"""무엇: 실행기 loopback 통합 · 입력: 127.0.0.1 503→200 · 출력: 실제 client 재시도 · 계약 §4-2·⑤d."""

from dataclasses import replace
import errno
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest

from jeveval.client.http import post
from jeveval.io.records import read_attempts
from tests.run.executor_support import Harness


class Handler(BaseHTTPRequestHandler):
    """두 응답만 내는 로컬 합성 서버다."""

    def log_message(self, *args):
        """시험 stderr를 오염시키지 않는다."""

    def do_POST(self):
        """첫 호출은 Retry-After 0과 503, 다음은 유효한 systemone 답을 보낸다."""
        self.server.bodies.append(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.paths.append(self.path)
        code = 503 if len(self.server.bodies) == 1 else 200
        raw = b'{"answers":{"is_ready":{"type":"noul","noul":0.8}}}'
        self.send_response(code)
        self.send_header("Retry-After", "0")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def test_real_client_503_then_200(tmp_path, env):
    """외부 네트워크 없이 실제 HTTP client를 실행기에 주입한다."""
    try:
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    except OSError as exc:
        if exc.errno in (errno.EACCES, errno.EPERM):
            pytest.skip("sandbox denies loopback bind")
        raise
    server.bodies, server.paths = [], []
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        h = Harness(tmp_path, env)
        cfg = replace(env.cfg, base_url=f"http://127.0.0.1:{server.server_port}")
        summary = h.run(cfg=cfg, post=post)
        assert summary.n_sent == 2 and summary.by_status == {"ok": 1}
        assert h.waits == [0] and server.bodies == [env.plan.body] * 2
        assert server.paths == ["/v1/systemone"] * 2
        assert [r.http_status for r in read_attempts(tmp_path / "dev/attempts.jsonl")[0]] == [503, 200]
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
