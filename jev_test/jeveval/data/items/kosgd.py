"""무엇: KoSGD 항목 · 입력: USER 행·분할·task·목록 · 출력: 단계별 Item · 계약 §6-2·§7-2."""

from jeveval.data.items.common import assemble, fields, questions
from functools import partial

from jeveval.score.labels import gold, ongoing_two
from jeveval.types import Item, ItemFields, SourceRow, SplitPlan, TaskSpec


def _catalog(lists):
    catalog, options = lists["kosgd_catalog"], lists["catalog_intents_plus_none"]
    order = [intent["id"] for service in catalog for intent in service["intents"]]
    if order != [key for key in options if key != "NONE"]:
        raise ValueError("KoSGD catalog order mismatch")
    return catalog, options


def _previous(row, bucket, options, rules):
    earlier = [r for r in bucket if r.fields["turn_index"] < row.fields["turn_index"]]
    if not earlier:
        return ["NONE", "NONE"]
    previous = max(earlier, key=lambda r: r.fields["turn_index"])
    return [gold(label, [previous], {}, options, rules) for label in ("ongoing_slot_1", "ongoing_slot_2")]


def build_items(rows: list[SourceRow], plan: SplitPlan, task: TaskSpec,
                lists: dict, rules: dict) -> dict[str, list[Item]]:
    """전체판·행동판 모두 같은 카탈로그와 직전 USER 고정 칸 기준선을 쓴다."""
    catalog, options = _catalog(lists)
    rules = {**rules, "ongoing_two": partial(ongoing_two,
             catalog_order=[key for key in options if key != "NONE"])}

    def make(selected, bucket) -> ItemFields:
        row = selected[0]
        state = dict(dialogue=row.fields["dialogue"], catalog=catalog)
        baseline = {"copy_prev": _previous(row, bucket, options, rules)}
        return fields(state, questions(selected, task, lists, rules=rules), service=row.fields["services"],
                      baseline=baseline)

    return assemble(rows, plan, task, make)
