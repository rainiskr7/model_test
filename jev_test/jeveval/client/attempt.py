"""무엇: 시도 기록 구성 · 입력: 관측값·executor 식별자/terminal · 출력: AttemptRecord · 계약 §5-3."""

from jeveval.types import AttemptRecord, AttemptResult


def to_attempt_record(result: AttemptResult, *, call_id, logical_id, attempt,
                      session_id, terminal, request_sha256) -> AttemptRecord:
    """전송 오류·HTTP 코드를 함께 보존하고 정책은 호출자가 정한 그대로 쓴다."""
    return AttemptRecord.from_dict(dict(result.to_dict(), call_id=call_id,
        logical_id=logical_id, attempt=attempt, session_id=session_id,
        terminal=terminal, request_sha256=request_sha256))
