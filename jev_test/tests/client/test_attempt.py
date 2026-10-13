"""무엇: 시도 기록 변환 · 입력: 합성 관측·executor 정책 · 출력: 독립 사본 · 계약 §5-3·§5-5b."""

import pytest

from jeveval.client.attempt import to_attempt_record
from jeveval.types import AttemptRecord, AttemptResult


@pytest.mark.parametrize("terminal", [True, False])
def test_preserves_partial_response_and_injected_policy(terminal):
    result = AttemptResult("start", "end", 123.0, 503, "1", "timeout", {"b64": "/w=="})
    record = to_attempt_record(result, call_id="s:g:i/q", logical_id="s:g:i", attempt=3,
        session_id="session", terminal=terminal, request_sha256="a" * 64)
    assert record.to_dict() == dict(result.to_dict(), call_id="s:g:i/q", logical_id="s:g:i",
        attempt=3, session_id="session", terminal=terminal, request_sha256="a" * 64)
    assert AttemptRecord.from_dict(record.to_dict()) == record
    record.response_raw["b64"] = ""
    assert result.response_raw == {"b64": "/w=="}
