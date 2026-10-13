"""무엇: 대표·분할·진단 조립 · 입력: 행/묶음/풀/규칙 · 출력: SplitPlan · 계약 §6."""

from collections import Counter, defaultdict
from copy import deepcopy
import math
import random

from jeveval.types import Groups, PoolResult, SourceRow, SplitPlan


def _representatives(groups, pool, seed, set_name, fixed):
    """대표는 문자열 구성원 정렬 후 독립 seed로 고른다."""
    selected = {s["dialogue_id"]: str(s["turn_index"]) for s in fixed or []}
    result = {}
    for gid in sorted(pool.group_ids):
        if fixed is not None:
            item = selected[gid]
            if item not in groups.members[gid]:
                raise ValueError(f"fixed representative not in group: {gid}")
        else:
            rng = random.Random(f"{seed}:{set_name}:rep:{gid}")
            item = rng.choice(sorted(groups.members[gid]))
        result[gid] = f"{set_name}:{gid}:{item}"
    return result


def _shuffled_groups(group_ids, seed, set_name):
    """fixture의 중간 순서와 같은 shuffle을 수행한다. 저장 때 따로 정렬한다."""
    ids = sorted(group_ids)
    random.Random(f"{seed}:{set_name}:split").shuffle(ids)
    return ids


def _label_conflicts(rows, groups, label_field):
    """원본 라벨 집합이 다른 묶음을 풀 선택과 독립적으로 센다."""
    labels = defaultdict(set)
    if label_field is None:
        return set()
    for row in rows:
        value = row.fields[label_field]
        label_set = value if isinstance(value, list) else [value]
        labels[groups.row_to_group[row.row_id]].add(tuple(sorted(set(label_set))))
    return {gid for gid, variants in labels.items() if len(variants) > 1}


def _demotions(positive_counts, min_positive):
    """양성이 경계 미만인 감정을 이름순으로 반환한다."""
    return sorted(name for name, count in positive_counts.items() if count < min_positive)


def _kote_demotions(rows, representatives, config, label_names):
    """풀 대표 하나당 라벨별 양성을 한 번씩 센다. 비대표는 세지 않는다."""
    if not config:
        return []
    if label_names is None or any(n not in label_names for n in config["emotions"]):
        raise ValueError("unknown demotion emotion or missing label names")
    counts = Counter({name: 0 for name in config["emotions"]})
    by_id = {row.row_id: row for row in rows}
    for logical_id in representatives.values():
        labels = by_id[logical_id.rsplit(":", 1)[1]].fields["labels_majority"]
        for name in set(labels):
            if name not in label_names:
                raise ValueError("KOTE unknown majority emotion")
            if name in counts:
                counts[name] += 1
    return _demotions(counts, config["min_positive"])


def build_split_plan(rows: list[SourceRow], groups: Groups, pool: PoolResult,
                     set_name: str, set_cfg: dict, seed: int, dev_fraction: float,
                     fixed: list[dict] | None = None,
                     label_names: list[str] | None = None) -> SplitPlan:
    """전체 행 통계와 평가 풀만 담은 분할 계획을 만든다."""
    if isinstance(dev_fraction, bool) or not 0 <= dev_fraction <= 1:
        raise ValueError("dev_fraction must be between 0 and 1")
    if not set_name or ":" in set_name:
        raise ValueError("set name must not contain ':'")
    if set_cfg["pool"]["kind"] == "fixed_selection" and fixed is None:
        raise ValueError("fixed_selection requires selected turns")
    representatives = _representatives(groups, pool, seed, set_name, fixed)
    shuffled = _shuffled_groups(pool.group_ids, seed, set_name)
    boundary = math.floor(dev_fraction * len(shuffled))
    members = {g: sorted(groups.members[g]) for g in sorted(pool.group_ids)}
    conflicts = _label_conflicts(rows, groups, set_cfg.get("label_field"))
    extra = []
    if set_name == "fc_call_decision" and set_cfg.get("extra", False):
        extra = sorted(f"{set_name}:{g}:{i}" for g, items in members.items()
                       for i in items if f"{set_name}:{g}:{i}" != representatives[g])
    notes = dict(n_rows=len(rows), n_groups_total=len(groups.members),
                 n_pool_groups=len(members), label_conflict_groups_total=len(conflicts),
                 label_conflict_groups_pool=len(conflicts.intersection(members)))
    demotions = _kote_demotions(rows, representatives, set_cfg.get("demotion"), label_names)
    return SplitPlan(set=set_name, seed=seed, pool_rule=deepcopy(set_cfg["pool"]),
                     allocation=dict(pool.allocation), groups=members,
                     representative=representatives, dev=sorted(shuffled[:boundary]),
                     test=sorted(shuffled[boundary:]), diagnostic_demotions=demotions,
                     extra=extra, notes=notes)


def check_split_plan(plan: SplitPlan) -> list[str]:
    """단계·대표·extra의 의미를 검사한다. extra 사용 여부는 셋 이름으로 추정하지 않는다."""
    errors = []
    if not plan.set or ":" in plan.set:
        errors.append("invalid set identifier")
    for stage in ("dev", "test", "extra"):
        values = getattr(plan, stage)
        if values != sorted(set(values)):
            errors.append(f"{stage}: expected sorted unique IDs")
    if set(plan.dev) & set(plan.test):
        errors.append("dev/test overlap")
    if set(plan.dev) | set(plan.test) != set(plan.groups):
        errors.append("dev/test union differs from groups")
    if set(plan.representative) != set(plan.groups):
        errors.append("representative keys differ from groups")
    members = set()
    for gid, items in plan.groups.items():
        valid = {f"{plan.set}:{gid}:{item}" for item in items}
        if not items or any(not isinstance(i, str) or not i or ":" in i for i in [gid, *items]):
            errors.append(f"invalid group or member IDs: {gid}")
        if plan.representative.get(gid) not in valid:
            errors.append(f"representative outside group: {gid}")
        members.update(valid)
    nonrepresentatives = members - set(plan.representative.values())
    if not set(plan.extra) <= nonrepresentatives:
        errors.append("extra contains unknown or representative IDs")
    return errors
