"""무엇: F1 성공 질문 관측 · 입력: outcome/Item · 출력: Observation · 계약 §7-2·7-7."""

from jeveval.score.kosgd_slots import fixed_gold
from jeveval.score.tasks import SLOT_LABELS
from jeveval.types import Observation


def observations(outcomes, items):
    """ok·정답 있는 성공 질문만, KoSGD 고정 칸과 KorFin pooled 관측을 보존한다."""
    result = []
    for row in outcomes:
        if row.status != "ok":
            continue
        item = items[row.logical_id]
        gold = dict(row.gold)
        slots = sorted((q for q in item.questions if q.label in SLOT_LABELS),
                       key=lambda q: SLOT_LABELS.index(q.label))
        if slots and all(q.gold is not None for q in slots):
            values = fixed_gold([q.gold for q in slots], [k for k in slots[0].options if k != "NONE"])
            gold.update(zip((q.id for q in slots), values))
        for q in item.questions:
            if q.role != "success" or gold[q.id] is None or (
                    item.set == "fc_call_decision" and q.label == "fc:tool"):
                continue
            result.append(Observation(row.logical_id, row.group_id, q.id, row.answer[q.id], gold[q.id]))
            if item.set == "korfin_asc" and q.label == "korfin:sentiment":
                result.append(Observation(row.logical_id, row.group_id, "aspect", row.answer[q.id], gold[q.id]))
    return result


def question_ids(items):
    """빈 코호트에서도 성공 질문의 null F1 셀을 남긴다."""
    ids = {q.id for item in items.values() for q in item.questions if q.role == "success"
           and not (item.set == "fc_call_decision" and q.label == "fc:tool")}
    if any(item.set == "korfin_asc" for item in items.values()):
        ids.add("aspect")
    return sorted(ids)
