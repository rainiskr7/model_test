"""무엇: 순수 재시도 정책 · 입력: 한 시도·누적 번호/상한 · 출력: Decision · 계약 §4-2·§5-5b."""

import math
import re

from jeveval.types import AttemptRecord, AttemptResult, Decision

MAX_ATTEMPTS = 5


def _retry_seconds(value):
    """십진 정수 초 또는 기존 기록의 음 아닌 정수값 숫자만 인정한다."""
    if isinstance(value, str) and re.fullmatch(r"[0-9]+", value):
        return int(value)
    if type(value) is int and value >= 0:
        return value
    if type(value) is float and math.isfinite(value) and value >= 0 and value.is_integer():
        return value
    return None


def decide(result: AttemptRecord | AttemptResult, attempt: int,
           max_attempts: int = MAX_ATTEMPTS) -> Decision:
    """부분 HTTP 응답의 전송 오류도 우선 재시도하며 마지막 시도에는 대기하지 않는다."""
    if (type(max_attempts) is not int or max_attempts < 1
            or type(attempt) is not int or not 1 <= attempt <= max_attempts):
        raise ValueError("attempt must be within 1..max_attempts")
    retry = result.transport_error is not None or result.http_status in (503, 529)
    if not retry or attempt == max_attempts:
        return Decision(True, None)
    seconds = _retry_seconds(result.retry_after)
    return Decision(False, seconds if seconds is not None else 2 ** (attempt - 1))
