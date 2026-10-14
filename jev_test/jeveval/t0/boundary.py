"""무엇: T0 길이 경계 판정 · 입력: 잘리기 전 길이/HTTP/길이 상태 · 출력: 상태 · 계약 §8-7 T-g."""

import re

from jeveval.types.t0 import T0Boundary, T0Observation


def judge_boundary(boundary: T0Boundary, observation: T0Observation):
    """질문별 길이 중 최대가 요청 거부를 결정한다. usage 합은 입력도 판정도 아니다."""
    if boundary.lengths is None:
        return "INCOMPLETE"
    if (type(boundary.limit) is not int or boundary.limit <= 0 or not boundary.lengths
            or any(type(n) is not int or n < 0 for n in boundary.lengths)
            or max(boundary.lengths) not in (boundary.limit, boundary.limit + 1)
            or boundary.overflow not in ("reject", "truncate_tail")):
        raise ValueError("invalid boundary measurement")
    if observation.transport_error or observation.http_status is None or observation.http_status >= 500:
        return "INCOMPLETE"
    if observation.length_status is None and (max(boundary.lengths) == boundary.limit or boundary.overflow == "truncate_tail"):
        return "INCOMPLETE"
    if max(boundary.lengths) == boundary.limit:
        ok = observation.http_status == 200 and observation.length_status == "ok"
    elif boundary.overflow == "truncate_tail":
        ok = observation.http_status == 200 and observation.length_status == "truncated"
    else:
        rule = boundary.input_limit_response
        if rule is None:
            return "INCOMPLETE"
        ok = observation.http_status == rule["status"] and re.search(rule["body_regex"], observation.response_raw)
    return "PASS" if ok else "FAIL"
