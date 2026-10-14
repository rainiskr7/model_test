"""무엇: T0 분포/오차 도메인 · 입력: 검증된 답 · 출력: 순서 고정 벡터 · 계약 §8-7 T-e/f."""

import math


def nonnegative(value):
    try:
        return type(value) in (int, float) and math.isfinite(value) and value >= 0
    except OverflowError:
        return False


def within(value, bound):
    """뺄셈의 부동소수점 경계만 보완한다. 허용폭 0은 정확한 0만 허용한다."""
    return value <= bound or math.isclose(value, bound, rel_tol=1e-12, abs_tol=0.0)


def vector(question, answer):
    """noul true/false, choice 코드포인트 ID, score 숫자 수준 순서. 재정규화하지 않는다."""
    if question["type"] == "noul":
        return [answer["noul"], 1 - answer["noul"]]
    keys = (sorted(question["criteria"]) if question["type"] == "choice"
            else [str(i) for i in range(len(question["criteria"]))])
    return [answer["probabilities"][key] for key in keys]


def status_of(statuses, *, has_reference=True):
    """확정 위반은 미완료보다 우선하고 참조 부재만 PARTIAL로 표시한다."""
    values = set(statuses)
    if not values <= {"PASS", "FAIL", "INCOMPLETE", "PARTIAL"}:
        raise ValueError("invalid T0 status")
    for status in ("FAIL", "INCOMPLETE"):
        if status in values:
            return status
    return "PASS" if has_reference else "PARTIAL"
