"""감사 프로세스의 네트워크 경계와 executor 가짜 post 포착. 추론은 호출하지 않는다."""

from contextlib import contextmanager
import socket
from unittest.mock import patch


def refuse(*args, **kwargs):
    raise RuntimeError("offline audit forbids network")


@contextmanager
def guard():
    from jeveval.client import http
    with patch.object(http, "post", refuse), patch.object(socket.socket, "connect", refuse), \
            patch.object(socket.socket, "connect_ex", refuse), patch.object(socket, "create_connection", refuse):
        yield


def capture(plan, cfg):
    """실제 executor의 post 인자를 포착한다. 기록 쓰기는 메모리 sink로 대체한다."""
    from dataclasses import replace
    from jeveval.run.executor import execute_call
    from jeveval.types import AttemptResult, LengthInfo, RetryPolicy
    class Measure:
        def measure(self, p):
            return LengthInfo(1, 1, cfg.limit["tokens"], 0)
    bodies = []
    def post(url, body, timeout, headers=None):
        bodies.append(body)
        return AttemptResult("2026-10-19T00:00:00Z", "2026-10-19T00:00:00Z", 0., 400, None, None, "{}")
    captured = []
    execute_call(plan, [], cfg=replace(cfg, base_url="http://offline.invalid"), measurer=Measure(),
                 post=post, sleep=refuse, session_id="audit", headers={}, timeout=1,
                 policy=RetryPolicy(1, [], []), record=captured.append)
    if len(bodies) != 1:
        raise ValueError("executor did not hand off one body")
    return bodies[0]
