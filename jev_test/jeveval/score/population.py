"""무엇: ok 코호트 점수 · 입력: outcome/final/Item · 출력: Population/ScoreTable · 계약 §7-1~3·7-6."""

from collections import Counter
from copy import deepcopy

from jeveval.score.calibration import calibrate
from jeveval.score.f1 import macro_f1
from jeveval.score.kosgd_slots import judge_slots
from jeveval.score.tasks import SLOT_LABELS, outcome
from jeveval.types import FinalRecord, Item, ParsedAnswer, Population, QStats, RequestOutcome, ScoreTable


def qstats(question_id, role, type, pairs: list[tuple[ParsedAnswer, str | None]],
           n_choice_not_argmax: int) -> QStats:
    """호출자가 ok 코호트를 넘긴다. 동결 FunctionChat 도구 ID는 tool이다."""
    if isinstance(n_choice_not_argmax, bool) or not isinstance(n_choice_not_argmax, int) or n_choice_not_argmax < 0:
        raise ValueError("expected nonnegative warning count")
    scored = [(p, g) for p, g in pairs if g is not None]
    parsed, gold = [p for p, _ in scored], [g for _, g in scored]
    f1 = macro_f1(gold, [p.answer for p in parsed])
    return QStats(role, type, len(scored), len(pairs) - len(scored),
                  dict(num=sum(p.answer == g for p, g in scored), den=len(scored)),
                  None if question_id == "tool" else f1.macro_f1, f1.class_stats,
                  calibrate(parsed, gold).to_dict(),
                  dict(choice_not_argmax=n_choice_not_argmax if type == "choice" else 0))


def _stats(qid, role, kind, pairs):
    warnings = sum(p.type == "choice" and p.probs[p.answer] < max(p.probs.values()) - 1e-9
                   for p, _ in pairs)
    return qstats(qid, role, kind, pairs, warnings)


def _slots(item):
    return sorted((q for q in item.questions if q.label in SLOT_LABELS),
                  key=lambda q: SLOT_LABELS.index(q.label))


def _specific(set_name, items):
    if set_name == "kosgd" and any(_slots(i) for i in items.values()):
        return dict(bundle_correct=dict(num=0, den=0), order_only_bundles=0,
                    copy_baseline_bundle_correct=dict(num=0, den=0))
    if set_name == "fc_call_decision":
        return dict(tool_acc_on_call=dict(num=0, den=0), none_acc_on_noncall=dict(num=0, den=0))
    if set_name == "korfin_asc":
        return dict(aspect_not_in_text=dict(n_scored=0, wrong=dict(num=0, den=0)))
    return {}


def _add_ratio(ratio, correct):
    ratio["num"] += int(correct)
    ratio["den"] += 1


def _slot_gold(item, parsed, specific):
    slots = _slots(item)
    gold = {q.id: q.gold for q in item.questions}
    if not slots or all(q.gold is None for q in slots):
        return gold
    catalog = [key for key in slots[0].options if key != "NONE"]
    truth = [q.gold for q in slots if q.gold != "NONE"]
    judgement = judge_slots([parsed[q.id].answer for q in slots], truth, catalog)
    gold.update(zip((q.id for q in slots), judgement.fixed_gold))
    if specific:
        _add_ratio(specific["bundle_correct"], judgement.group_correct)
        specific["order_only_bundles"] += int(judgement.order_only)
        baseline = judge_slots(item.baseline["copy_prev"], truth, catalog)
        _add_ratio(specific["copy_baseline_bundle_correct"], baseline.group_correct)
    return gold


def _set_rows(set_name, item, parsed, gold, specific):
    if set_name == "fc_call_decision":
        by_label = {q.label: q.id for q in item.questions}
        action, tool = by_label["fc:type_of_output"], by_label["fc:tool"]
        if gold[action] is not None and gold[tool] is not None:
            key = "tool_acc_on_call" if gold[action] == "call" else "none_acc_on_noncall"
            _add_ratio(specific[key], parsed[tool].answer == gold[tool])
    if set_name == "korfin_asc":
        flags = item.meta["flags"]
        for qid, g in gold.items():
            if g is not None and f"aspect_not_in_text:{qid}" in flags:
                cell = specific["aspect_not_in_text"]
                cell["n_scored"] += 1
                _add_ratio(cell["wrong"], parsed[qid].answer != g)


def _inputs(outcomes, finals, items, certified, unit, set_name):
    if unit not in ("group_representative", "row") or (certified and unit != "group_representative"):
        raise ValueError("invalid population unit/certified")
    by_id = {f.logical_id: f for f in finals}
    ids = {r.logical_id for r in outcomes}
    if len(by_id) != len(finals) or len(ids) != len(outcomes) or ids != by_id.keys() or not ids <= items.keys():
        raise ValueError("population outcome/final/Item IDs differ or duplicate")
    if certified and any(r.stage != "test" for r in outcomes):
        raise ValueError("certified population requires test representatives")
    if unit == "group_representative" and len({r.group_id for r in outcomes}) != len(outcomes):
        raise ValueError("expected unique group representatives")
    headers, pairs = {}, {}
    for lid, item in items.items():
        if item.set != set_name or lid != f"{item.set}:{item.group_id}:{item.item_id}":
            raise ValueError("population Item set/logical_id mismatch")
        for q in item.questions:
            header = (q.role, q.type, q.label)
            if q.id in headers and headers[q.id] != header:
                raise ValueError("inconsistent question metadata")
            headers[q.id], pairs[q.id] = header, []
    return by_id, headers, pairs


def population(*, outcomes: list[RequestOutcome], finals: list[FinalRecord],
               items: dict[str, Item], certified: bool, unit: str, set_name: str) -> Population:
    """입력은 호출자가 선택한 모집단. Item은 빈 코호트의 질문 틀을 위해 상위 집합도 허용한다."""
    by_id, headers, pairs = _inputs(outcomes, finals, items, certified, unit, set_name)
    specific = _specific(set_name, items)
    for row in outcomes:
        final, item = by_id[row.logical_id], items[row.logical_id]
        if outcome(final, item, row.stage) != row:
            raise ValueError("population outcome differs from final/Item")
        if row.status != "ok":
            continue
        parsed = {qid: p for c in final.calls for qid, p in c.answers_parsed.items()}
        gold = _slot_gold(item, parsed, specific if set_name == "kosgd" else {})
        for q in item.questions:
            pairs[q.id].append((parsed[q.id], gold[q.id]))
        _set_rows(set_name, item, parsed, gold, specific)
    questions = {}
    for qid, (role, kind, label) in sorted(headers.items()):
        stats_id = "tool" if set_name == "fc_call_decision" and label == "fc:tool" else qid
        questions[qid] = _stats(stats_id, role, kind, pairs[qid])
    pooled = {}
    if set_name == "korfin_asc":
        aspect = [pair for qid in sorted(pairs) for pair in pairs[qid]
                  if headers[qid][2] == "korfin:sentiment"]
        pooled["aspect"] = _stats("aspect", "success", "choice", aspect)
    counts = Counter(r.status for r in outcomes)
    scored = [r for r in outcomes if r.status == "ok" and not r.mask_empty]
    return Population(certified, unit,
                      dict(n_sampled=len(outcomes), by_status={s: counts[s] for s in
                           ("ok", "rejected", "truncated", "error")},
                           n_empty_mask=sum(r.mask_empty for r in outcomes)),
                      dict(n_scored=len(scored), wrong=dict(num=sum(r.wrong for r in scored), den=len(scored))),
                      questions, pooled, specific)


def score_table(*, model, set, variant, run_id, populations: dict[str, Population], cost: dict) -> ScoreTable:
    return ScoreTable("scores/1", model, set, variant, run_id, deepcopy(populations), deepcopy(cost))
