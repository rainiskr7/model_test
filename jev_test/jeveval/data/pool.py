"""무엇: 평가 풀 선정 · 입력: Groups·규칙·층/선정 · 출력: PoolResult · 계약 §6."""

from collections import defaultdict
import random

from jeveval.types import Groups, PoolResult


def _fixed_ids(groups: Groups, fixed: list[dict] | None) -> list[str]:
    """없는 대화·중복·SYSTEM·범위 밖 선정은 USER 구성원 검사로 거부한다."""
    if not fixed:
        raise ValueError("fixed_selection must not be empty")
    seen = set()
    for selection in fixed:
        gid, turn = selection["dialogue_id"], selection["turn_index"]
        if gid in seen:
            raise ValueError(f"duplicate selected dialogue: {gid}")
        if type(turn) is not int or turn < 0:
            raise ValueError("selected turn_index must be a nonnegative integer")
        if gid not in groups.members or str(turn) not in groups.members[gid]:
            raise ValueError(f"selected USER turn does not exist: {gid}#{turn}")
        seen.add(gid)
    return sorted(seen)


def _proportional(ids, cap, strata, prefix) -> PoolResult:
    """최대 나머지는 정수 나머지로 비교하고 동률은 층 이름순으로 푼다."""
    if strata is None or set(strata) != set(ids):
        raise ValueError("strata must cover every group exactly")
    buckets = defaultdict(list)
    for gid in ids:
        if not isinstance(strata[gid], str):
            raise ValueError("stratum names must be strings")
        buckets[strata[gid]].append(gid)
    counts = {h: len(buckets[h]) for h in sorted(buckets)}
    total = len(ids)
    if cap >= total:
        return PoolResult(ids, counts)
    allocation = {h: cap * n // total for h, n in counts.items()}
    order = sorted(counts, key=lambda h: (-(cap * counts[h] % total), h))
    for h in order[:cap - sum(allocation.values())]:
        allocation[h] += 1
    chosen = []
    for h, count in allocation.items():
        chosen.extend(random.Random(f"{prefix}:{h}").sample(sorted(buckets[h]), count))
    return PoolResult(chosen, allocation)


def select_pool(groups: Groups, pool_cfg: dict, seed: int, set_name: str,
                strata: dict[str, str] | None = None,
                fixed: list[dict] | None = None, excluded: set[str] | None = None) -> PoolResult:
    """strata는 group_id→층 이름, fixed는 감사 selected_turns 목록이다."""
    ids = sorted(groups.members)
    if not ids:
        raise ValueError("empty population")
    kind = pool_cfg["kind"]
    if kind == "fixed_selection":
        ids = _fixed_ids(groups, fixed)
        if pool_cfg.get("exclude") and excluded is None:
            raise ValueError("fixed_selection exclusion evidence required")
        if set(ids) & (excluded or set()):
            raise ValueError("fixed_selection intersects excluded dialogue pool")
    elif kind in {"simple_cap", "proportional"}:
        cap = pool_cfg.get("cap")
        if type(cap) is not int or cap <= 0:
            raise ValueError("cap must be a positive integer")
        prefix = f"{seed}:{set_name}:pool"
        if kind == "proportional":
            return _proportional(ids, cap, strata, prefix)
        if cap < len(ids):
            ids = random.Random(prefix).sample(ids, cap)
    elif kind != "all":
        raise ValueError(f"unknown pool kind: {kind}")
    return PoolResult(ids, {"all": len(ids)})
