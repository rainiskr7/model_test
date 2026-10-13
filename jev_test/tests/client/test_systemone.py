"""무엇: systemone 전송 경계 · 입력: 요청·가짜 post · 출력: 경로·원 바이트·해시 · 계약 §2-1·§5-5b."""

import hashlib

from jeveval.client.systemone import send_systemone, systemone_url
from jeveval.contract.request import request_bytes
from jeveval.types import AttemptResult, Request


def test_request_bytes_url_hash_and_single_post():
    request = Request("model", " 원문\n", {"z": {"type": "noul"}, "a": {"type": "noul"}})
    result = AttemptResult("start", "end", 1.0, 503, "1", None, "{}")
    calls = []

    def post(url, body, timeout):
        calls.append((url, body, timeout))
        return result

    digest, received = send_systemone("http://127.0.0.1:9/", request, post=post)
    assert calls == [("http://127.0.0.1:9/v1/systemone", request_bytes(request), 600)]
    assert digest == hashlib.sha256(calls[0][1]).hexdigest() and received is result
    assert systemone_url("http://127.0.0.1:9") == calls[0][0]
