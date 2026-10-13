"""무엇: 순수 resume 선검사 · 입력: 전체 계획·기록·예산 · 출력: 오류 목록 · 계약 §8-6 B·⑤d R1."""

from jeveval.types import AttemptRecord, CallPlan, FinalRecord


def check_resume(plans: list[CallPlan], attempts: list[AttemptRecord],
                 finals: list[FinalRecord], max_attempts: int) -> list[str]:
    """완료 항목과 로컬 오류도 포함하여 첫 전송/쓰기 전에 모든 기록을 대조한다."""
    if type(max_attempts) is not int or max_attempts < 1:
        return ["invalid max_attempts"]
    errors, previous = [], {}
    by_call = {p.call_id: p for p in plans}
    if len(by_call) != len(plans):
        errors.append("duplicate planned call_id")
    logical_ids = {p.logical_id for p in plans}
    final_ids = [f.logical_id for f in finals]
    if len(set(final_ids)) != len(final_ids):
        errors.append("duplicate final logical_id")
    if set(final_ids) - logical_ids:
        errors.append("final outside current items")
    for row in attempts:
        plan, last = by_call.get(row.call_id), previous.get(row.call_id)
        if plan is None:
            errors.append("attempt outside current plans")
        elif (row.logical_id != plan.logical_id or row.request_sha256 != plan.request_sha256
              or plan.local_errors):
            errors.append("attempt does not match current plan")
        if type(row.attempt) is not int or row.attempt != (last.attempt + 1 if last else 1):
            errors.append("nonconsecutive attempt")
        if row.attempt > max_attempts:
            errors.append("attempt budget exceeded")
        if last is not None and last.terminal:
            errors.append("attempt after terminal")
        previous[row.call_id] = row
    return list(dict.fromkeys(errors))
