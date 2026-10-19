"""네트워크 거부 훅 검증. 실제 연결은 시도하지 않는다."""

import socket
import pytest

from audits.audit_v4.offline import guard
from jeveval.client import http


def test_network_and_real_post_are_denied():
    with guard():
        with pytest.raises(RuntimeError): http.post("http://invalid", b"", 1)
        with socket.socket() as s:
            with pytest.raises(RuntimeError): s.connect(("127.0.0.1", 1))
        with pytest.raises(RuntimeError): socket.create_connection(("127.0.0.1", 1))
