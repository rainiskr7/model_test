"""무엇: 재시도 정책 스키마 검사 · 입력: configs/policy.yaml 객체 · 출력: RetryPolicy 또는 오류 목록 · 계약 §4-2·§8-1."""

import math

from jeveval.types import RetryPolicy


def validate_retry_policy(data) -> RetryPolicy | list[str]:
    """닫힌 키·양의 정수 예산·고유 HTTP 상태·비최종 시도마다 하나의 대기만 받는다."""
    if not isinstance(data, dict) or set(data) != {"retry"} or not isinstance(data["retry"], dict):
        return ["policy requires exactly one mapping: retry"]
    retry = data["retry"]
    if set(retry) != {"max_attempts", "http_statuses", "backoff_seconds"}:
        return ["retry requires exactly max_attempts, http_statuses, backoff_seconds"]
    errors = []
    n, statuses, waits = retry["max_attempts"], retry["http_statuses"], retry["backoff_seconds"]
    if type(n) is not int or n < 1:
        errors.append("max_attempts must be a positive integer")
    if (not isinstance(statuses, list) or not statuses
            or any(type(s) is not int or not 100 <= s <= 599 for s in statuses)
            or len(set(statuses)) != len(statuses)):
        errors.append("http_statuses must be unique HTTP status integers")
    if (not isinstance(waits, list)
            or any(type(w) not in (int, float) or not math.isfinite(w) or w < 0 for w in waits)
            or (type(n) is int and n >= 1 and len(waits) != n - 1)):
        errors.append("backoff_seconds must list one nonnegative wait per non-final attempt")
    return errors or RetryPolicy(n, list(statuses), [float(w) for w in waits])
