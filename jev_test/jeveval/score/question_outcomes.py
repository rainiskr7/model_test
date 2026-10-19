"""무엇: 질문 관측 투영 · 입력: FinalRecord+Item+단계 · 출력: QuestionOutcome · 계약 §7-4b."""

from dataclasses import replace
import json

from jeveval.score.kosgd_slots import judge_slots
from jeveval.score.tasks import SLOT_LABELS, outcome
from jeveval.types.outcomes import QuestionOutcome


def _unit(row, qs, parsed):
    first, bundle = qs[0], len(qs) == 2
    gold, answer, confidence, wrong = first.gold, None, None, None
    qid, label, kind = first.id, first.label, first.type
    if bundle:
        qid, label, kind = "ongoing_bundle", "ongoing_bundle", "bundle"
        if sum(q.gold is None for q in qs) == 1:
            raise ValueError("partially MISSING slots")
        gold = (None if first.gold is None else "NONE" if all(q.gold == "NONE" for q in qs)
                else json.dumps([q.gold for q in qs]))
    if row.valid:
        values = [parsed[q.id] for q in qs]
        confidence = min(p.confidence for p in values)
        answer = json.dumps([p.answer for p in values]) if bundle else values[0].answer
        if gold is not None:
            wrong = answer != gold
            if bundle:
                wrong = not judge_slots([p.answer for p in values], [q.gold for q in qs],
                                        [key for key in first.options if key != "NONE"]).group_correct
    return QuestionOutcome(row.logical_id, row.group_id, row.stage, row.status, row.valid,
                           qid, first.role, label, kind, gold, answer, confidence, wrong,
                           True, row.length_max, row.meta)


def observations(finals, items, stage):
    """가변 질문은 합집합으로 펼치고 미존재를 명시한다. 슬롯은 하나의 단위다."""
    if len({f.logical_id for f in finals}) != len(finals) or {f.logical_id for f in finals} != items.keys():
        raise ValueError("final/Item IDs differ")
    result, rows, headers = [], [], {}
    for final in finals:
        item = items[final.logical_id]
        row = outcome(final, item, stage)
        rows.append(row)
        parsed = {qid: p for call in final.calls for qid, p in (call.answers_parsed or {}).items()}
        slots = sorted([q for q in item.questions if q.label in SLOT_LABELS], key=lambda q: SLOT_LABELS.index(q.label))
        units = [[q] for q in item.questions if q.label not in SLOT_LABELS]
        if slots:
            if len(slots) != 2 or any(q.role != "success" for q in slots):
                raise ValueError("invalid slot bundle")
            units.append(slots)
        for qs in units:
            unit = _unit(row, qs, parsed)
            header = (unit.role, unit.label, unit.qtype)
            if unit.question_id in headers and headers[unit.question_id] != header:
                raise ValueError("inconsistent question metadata")
            headers[unit.question_id] = header
            result.append(unit)
    present = {(r.logical_id, r.question_id) for r in result}
    for row in rows:
        for qid, (role, label, kind) in headers.items():
            if (row.logical_id, qid) not in present:
                result.append(QuestionOutcome(row.logical_id, row.group_id, stage, row.status,
                    row.valid, qid, role, label, kind, None, None, None, None, False, row.length_max, row.meta))
    return result


def align(dev, test):
    """한 단계에만 있는 질문은 다른 단계 전체에 미존재 관측으로 채운다."""
    headers = {}
    for row in [*dev, *test]:
        header = (row.role, row.label, row.qtype)
        if row.question_id in headers and headers[row.question_id] != header:
            raise ValueError("question metadata differs between stages")
        headers[row.question_id] = header
    def fill(rows):
        result = list(rows)
        representatives = {r.logical_id: r for r in rows}
        present = {(r.logical_id, r.question_id) for r in rows}
        for lid, row in representatives.items():
            for qid, (role, label, kind) in headers.items():
                if (lid, qid) not in present:
                    result.append(replace(row, question_id=qid, role=role, label=label, qtype=kind,
                                          present=False, gold=None, answer=None, confidence=None, wrong=None))
        return result
    return fill(dev), fill(test)
