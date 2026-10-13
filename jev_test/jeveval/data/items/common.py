"""무엇: 항목 공통 조립·요약 · 입력: 행·분할·task/항목 · 출력: 단계별 항목/통계 · 계약 §6-2."""

from collections import Counter, defaultdict
from copy import deepcopy

from jeveval.data.expand import expand_questions
from jeveval.data.grouping import group_rows
from jeveval.data.split import check_split_plan
from jeveval.score.labels import gold
from jeveval.types import Item


def questions(rows, task, lists, item_options=None, bindings=()):
    """해당 항목의 원본 행을 정답 함수에 연결한다."""
    return expand_questions(task, lists, item_options, bindings,
                            lambda label, binding, options: gold(label, rows, binding, options))


def fields(state, bound, service=None, stratum=None, flags=(), baseline=None):
    """닫힌 meta와 원본에 별칭이 없는 항목 필드를 만든다."""
    return deepcopy(dict(state_fields=state, questions=bound, baseline=baseline,
                         meta=dict(service=service, stratum=stratum, flags=sorted(set(flags)))))


def _buckets(rows, plan, task):
    """분할 의미와 풀 구성원 일치 검사를 조립 전에 수행한다."""
    errors = check_split_plan(plan)
    if errors:
        raise ValueError("; ".join(errors))
    if plan.set != task.set or any(row.set != task.set for row in rows):
        raise ValueError("row/plan/task set mismatch")
    groups = group_rows(rows, task.group_key)
    if any(groups.members.get(g) != members for g, members in plan.groups.items()):
        raise ValueError("plan.groups mismatch")
    buckets = defaultdict(list)
    for row in rows:
        buckets[groups.row_to_group[row.row_id]].append(row)
    return buckets


def _selected(bucket, item_id, rule):
    """KorFin은 SRC의 모든 행, 나머지는 대표/extra의 한 행을 선택한다."""
    if rule == "SRC":
        return bucket
    selected = [row for row in bucket if
                (str(row.fields["turn_index"]) if rule == "dialogue_id" else row.row_id) == item_id]
    if len(selected) != 1:
        raise ValueError("logical_id does not identify one source row")
    return selected


def assemble(rows, plan, task, make, allow_extra=False):
    """분할에 적힌 순서로만 항목을 만들고 원본 묶음 전체를 callback에 전달한다."""
    buckets = _buckets(rows, plan, task)
    if plan.extra and not allow_extra:
        raise ValueError("this item builder does not support extra")
    ids = {stage: [plan.representative[g] for g in getattr(plan, stage)] for stage in ("dev", "test")}
    ids["extra"] = plan.extra
    result = {stage: [] for stage in ids}
    for stage, logical_ids in ids.items():
        for logical_id in logical_ids:
            parts = logical_id.split(":")
            if len(parts) != 3 or parts[0] != task.set:
                raise ValueError("invalid logical_id")
            _, gid, iid = parts
            bucket = buckets[gid]
            selected = _selected(bucket, iid, task.group_key)
            result[stage].append(Item(task.set, gid, iid, **make(selected, bucket)))
    return result


def conflict_flags(rows, label_field):
    """묶음 전체의 라벨 집합을 비교하며 중복 라벨·순서는 무시한다."""
    variants = set()
    for row in rows:
        labels = row.fields.get(label_field)
        kind = int if label_field == "label" else str
        if not isinstance(labels, list) or any(type(label) is not kind for label in labels):
            raise ValueError(f"invalid label field: {label_field}")
        variants.add(tuple(sorted(set(labels))))
    return ["label_conflict_group"] if len(variants) > 1 else []


def summarize(items):
    """원문 없이 단계별 질문 정답·flag 항목 수·층·baseline 수를 집계한다."""
    return {stage: _stage_summary(stage_items) for stage, stage_items in items.items()}


def _stage_summary(items):
    questions, flags, strata = {}, Counter(), Counter()
    for item in items:
        flags.update({flag.split(":", 1)[0] for flag in item.meta["flags"]})
        if item.meta["stratum"] is not None:
            strata[item.meta["stratum"]] += 1
        for q in item.questions:
            count = len(q.options) if q.type == "choice" else 2
            header = dict(role=q.role, type=q.type, n_options=count)
            if q.id not in questions:
                questions[q.id] = dict(**header, gold={"MISSING": 0})
            stats = questions[q.id]
            if any(stats[key] != value for key, value in header.items()):
                raise ValueError("inconsistent question summary shape")
            for label in (q.options if q.type == "choice" else ("true", "false")):
                stats["gold"].setdefault(label, 0)
            label = "MISSING" if q.gold is None else q.gold
            stats["gold"][label] = stats["gold"].get(label, 0) + 1
    return dict(n=len(items), questions=questions, flags=dict(sorted(flags.items())),
                stratum=dict(sorted(strata.items())) if strata else None,
                baseline=sum(item.baseline is not None for item in items))
