"""무엇: KoSGD 행동판 순수 파생 · 입력: 전체판 기록·질문·출처 · 출력: 독립 사본 · 계약 §5-4·§8-6 K·⑤d R2."""

from copy import deepcopy
from dataclasses import replace

from jeveval.types import FinalRecord


def derive_actions_only(full: FinalRecord, action_qids: list[str],
                        full_question_ids: list[str], derived_from: str) -> FinalRecord:
    """질문 존재는 원본 Item으로 확인하고 오류 상태와 호출의 원래 비용 관측값을 보존한다."""
    if (len(set(action_qids)) != len(action_qids)
            or len(set(full_question_ids)) != len(full_question_ids)
            or not set(action_qids) <= set(full_question_ids)):
        raise ValueError("invalid derived question IDs")
    calls = deepcopy(full.calls)
    if len(calls) == 1 and calls[0].call_id == full.logical_id:
        answers = calls[0].answers_parsed
        if answers is not None:
            if set(answers) != set(full_question_ids):
                raise ValueError("full answers differ from full questions")
            calls[0] = replace(calls[0], answers_parsed={q: a for q, a in answers.items() if q in action_qids})
    else:
        expected = [f"{full.logical_id}/{q}" for q in full_question_ids]
        if [c.call_id for c in calls] != expected:
            raise ValueError("full calls differ from full questions")
        selected = {f"{full.logical_id}/{q}" for q in action_qids}
        calls = [c for c in calls if c.call_id in selected]
    return replace(deepcopy(full), calls=calls, derived_from=derived_from)


def derive_stage(full_finals, items_full, action_qids, derived_from) -> list[FinalRecord]:
    """완료된 전체판과 Item 집합을 정확히 대조하고 final 순서로 파생한다."""
    items = {f"{i.set}:{i.group_id}:{i.item_id}": i for i in items_full}
    ids = [f.logical_id for f in full_finals]
    if len(items) != len(items_full) or len(set(ids)) != len(ids) or set(ids) != set(items):
        raise ValueError("full stage is incomplete or duplicated")
    return [derive_actions_only(f, action_qids, [q.id for q in items[f.logical_id].questions],
                                derived_from) for f in full_finals]
