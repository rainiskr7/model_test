"""무엇: T0 상태 합성 · 입력: 질문/사례 상태 목록·참조 유무 · 출력: PASS/FAIL/INCOMPLETE/PARTIAL · 계약 §8-7 T-f."""


def status_of(statuses, *, has_reference=True):
    """확정 위반은 미완료보다 우선하고 참조 부재만 PARTIAL로 표시한다."""
    values = set(statuses)
    if not values <= {"PASS", "FAIL", "INCOMPLETE", "PARTIAL"}:
        raise ValueError("invalid T0 status")
    for status in ("FAIL", "INCOMPLETE"):
        if status in values:
            return status
    return "PASS" if has_reference else "PARTIAL"
