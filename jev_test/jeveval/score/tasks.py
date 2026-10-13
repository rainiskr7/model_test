"""무엇: 요청 채점 · 입력: FinalRecord·Item·단계 · 출력: RequestOutcome · 계약 §7-1~3·§7-8·§8-6 D."""

from copy import deepcopy

from jeveval.score.kosgd_slots import judge_slots
from jeveval.types import FinalRecord, Item, RequestOutcome


SLOT_LABELS = ("ongoing_slot_1", "ongoing_slot_2")


def _mask(success):
    """칸 묶음의 부분 결측은 상태와 무관하게 거부한다 (§7-2)."""
    slots = [q for q in success if q.label in SLOT_LABELS]
    if slots:
        if len(slots) != 2 or {q.label for q in slots} != set(SLOT_LABELS):
            raise ValueError("KoSGD requires both slot questions")
        slots.sort(key=lambda q: SLOT_LABELS.index(q.label))
        missing = sum(q.gold is None for q in slots)
        if missing == 1:
            raise ValueError("KoSGD slot gold is partially MISSING")
        if missing == 2:
            slots = []
    regular = [q for q in success if q.label not in SLOT_LABELS and q.gold is not None]
    return regular, slots


def _answers(final, question_ids):
    """B1을 포함한 호출별 답을 합치되 중복·누락·남는 질문을 거부한다."""
    parsed = {}
    for call in final.calls:
        answers = call.answers_parsed or {}
        if parsed.keys() & answers.keys():
            raise ValueError("duplicate answer question ID across calls")
        parsed.update(answers)
    if parsed.keys() != question_ids:
        raise ValueError("answer question IDs differ from Item")
    return parsed


def outcome(final: FinalRecord, item: Item, stage: str) -> RequestOutcome:
    """정답 마스크와 별개로 성공 질문 전체의 확신 최솟값을 보존한다."""
    if final.logical_id != f"{item.set}:{item.group_id}:{item.item_id}":
        raise ValueError("final/Item logical_id mismatch")
    if stage not in ("dev", "test", "extra"):
        raise ValueError("stage must be dev, test or extra")
    roles = {q.id: q.role for q in item.questions}
    gold = {q.id: q.gold for q in item.questions}
    if len(gold) != len(item.questions):
        raise ValueError("duplicate Item question ID")
    success = [q for q in item.questions if q.role == "success"]
    if not success:
        raise ValueError("at least one success question required")
    regular, slots = _mask(success)
    mask_empty = not regular and not slots
    valid = final.status == "ok"
    answer = s = wrong = None
    if valid:
        parsed = _answers(final, gold.keys())
        answer = {qid: parsed[qid].answer for qid in gold}
        s = min(parsed[q.id].confidence for q in success)
        if not mask_empty:
            wrong = any(answer[q.id] != q.gold for q in regular)
            if slots:
                catalog = [key for key in slots[0].options if key != "NONE"]
                judgement = judge_slots([answer[q.id] for q in slots],
                                        [q.gold for q in slots if q.gold != "NONE"], catalog)
                wrong = wrong or not judgement.group_correct
    lengths = [call.length.length_tokens for call in final.calls if call.length is not None]
    return RequestOutcome(logical_id=final.logical_id, group_id=item.group_id, stage=stage,
                          status=final.status, valid=valid, mask_empty=mask_empty, s=s,
                          wrong=wrong, gold=gold, answer=answer,
                          length_max=max(lengths) if lengths else None,
                          meta=deepcopy(item.meta), roles=roles)
