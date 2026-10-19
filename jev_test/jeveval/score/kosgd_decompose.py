"""무엇: KoSGD 오류 분해 · 입력: 유효 final/Item · 출력: KosgdDecomposition · 계약 §7-6."""

from collections import Counter

from jeveval.score.kosgd_slots import judge_slots
from jeveval.score.tasks import SLOT_LABELS, outcome
from jeveval.types.report import KosgdDecomposition


def decompose(finals, items, stage):
    counts, errors = Counter(), Counter({k: 0 for k in ("duplicate", "replacement", "addition", "omission", "other")})
    grid, matched, ids, wrong_ids = [[0] * 3 for _ in range(3)], 0, [], []
    if len({f.logical_id for f in finals}) != len(finals):
        raise ValueError("duplicate decomposition ID")
    for final in finals:
        item = items[final.logical_id]
        row = outcome(final, item, stage)
        if not row.valid:
            raise ValueError("decomposition requires valid requests")
        slots = sorted([q for q in item.questions if q.label in SLOT_LABELS], key=lambda q: SLOT_LABELS.index(q.label))
        if len(slots) != 2 or any(q.gold is None for q in slots):
            raise ValueError("decomposition requires complete slot gold")
        predicted = [row.answer[q.id] for q in slots]
        truth = {q.gold for q in slots if q.gold != "NONE"}
        values = set(predicted) - {"NONE"}
        judged = judge_slots(predicted, list(truth), [k for k in slots[0].options if k != "NONE"])
        action_wrong = any(row.answer[q.id] != q.gold for q in item.questions
                           if q.role == "success" and q.type == "noul" and q.gold is not None)
        slot_wrong = not judged.group_correct
        counts[slot_wrong, action_wrong] += 1
        grid[len(truth)][sum(v != "NONE" for v in predicted)] += 1
        ids.append(final.logical_id)
        if slot_wrong or action_wrong:
            wrong_ids.append(final.logical_id)
        if slot_wrong:
            kind = ("duplicate" if judged.duplicate_non_none else
                    "replacement" if len(values) == len(truth) and values != truth else
                    "addition" if values > truth else "omission" if values < truth else "other")
            errors[kind] += 1
        matched += int(judged.duplicate_non_none and len(truth) == 1 and values == truth)
    return KosgdDecomposition(stage, counts[False, False], counts[True, False], counts[False, True],
                              counts[True, True], dict(errors), grid, matched, sorted(ids), sorted(wrong_ids))
