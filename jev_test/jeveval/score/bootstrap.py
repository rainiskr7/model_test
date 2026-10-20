"""무엇: 묶음 paired bootstrap · 입력: 시험 outcome/공통 ok 관측 · 출력: 차이·95% CI · 계약 §7-7·⑥a-2b R2."""

from collections import Counter, defaultdict
from itertools import combinations
import math
import random

from jeveval.score.f1 import macro_f1
from jeveval.types import Observation, RequestOutcome


def _percentile(values, p):
    values = sorted(values)
    position = (len(values) - 1) * p
    lo, hi = math.floor(position), math.ceil(position)
    return values[lo] + (values[hi] - values[lo]) * (position - lo)


def _bootstrap(models, groups, evaluate, seed, set_name, reps):
    if len(models) < 2 or type(reps) is not int or reps < 1:
        raise ValueError("bootstrap requires two models and positive integer reps")
    names, groups = sorted(models), sorted(groups)
    pairs = list(combinations(names, 2))
    draws = {pair: [] for pair in pairs}
    point = evaluate(groups)
    rng = random.Random(f"{seed}:boot:{set_name}")
    for _ in range(reps):
        values = evaluate(rng.choices(groups, k=len(groups)) if groups else [])
        for a, b in pairs:
            if values[a] is not None and values[b] is not None:
                draws[a, b].append(values[a] - values[b])
    result = []
    for a, b in pairs:
        values = draws[a, b]
        # 정의되지 않은 재표본을 버려 조건부 CI로 바꾸지 않는다.
        ci = [_percentile(values, p) for p in (.025, .975)] if len(values) == reps else None
        result.append(dict(models=[a, b], estimate=None if point[a] is None or point[b] is None
                           else point[a] - point[b], ci95=ci, n_defined=len(values)))
    return dict(models=names, n_groups=len(groups), reps=reps, pairs=result)


def coverage_diff(per_model: dict[str, list[RequestOutcome]], thresholds: dict[str, float | None],
                  *, seed, set_name, reps=2000) -> dict:
    """동일 시험 대표 전체를 요구하며 실패도 분모에 남긴다. 빈 마스크는 공통으로 제외한다."""
    if per_model.keys() != thresholds.keys():
        raise ValueError("threshold/model keys differ")
    indexed, reference = {}, None
    for model, rows in per_model.items():
        if any(r.stage != "test" for r in rows):
            raise ValueError("coverage requires test outcomes")
        if len({r.logical_id for r in rows}) != len(rows) or len({r.group_id for r in rows}) != len(rows):
            raise ValueError("coverage requires unique group representatives")
        signature = {r.logical_id: (r.group_id, r.mask_empty) for r in rows}
        if reference is not None and signature != reference:
            raise ValueError("coverage populations/group IDs/masks differ")
        reference = signature
        t = thresholds[model]
        if t is not None and (isinstance(t, bool) or not math.isfinite(t) or not 0 <= t <= 1):
            raise ValueError("invalid threshold")
        indexed[model] = {r.group_id: int(t is not None and r.status == "ok" and r.s >= t)
                          for r in rows if not r.mask_empty}
    groups = next(iter(indexed.values()), {})

    def evaluate(sample):
        return {m: sum(values[g] for g in sample) / len(sample) if sample else None
                for m, values in indexed.items()}

    return _bootstrap(per_model, groups, evaluate, seed, set_name, reps)


def f1_diff(per_model_obs: dict[str, list[Observation]], cohort_ids, *, seed, set_name,
            question_id, reps=2000, f1_defined=True) -> dict:
    """cohort_ids는 common_cohort의 결과. gold 있는 ok 관측만 넘기며 aspect 중복 관측을 보존한다."""
    cohort = set(cohort_ids)
    if len(cohort) != len(cohort_ids):
        raise ValueError("duplicate cohort logical_id")
    if not f1_defined:
        raise ValueError("FunctionChat tool macro-F1 is not defined")
    grouped, reference, membership = {}, None, {}
    for model, observations in per_model_obs.items():
        by_group, signature = defaultdict(list), Counter()
        for obs in observations:
            if obs.logical_id not in cohort:
                continue
            if obs.logical_id in membership and membership[obs.logical_id] != obs.group_id:
                raise ValueError("observation group IDs differ")
            membership[obs.logical_id] = obs.group_id
            if obs.question_id != question_id:
                continue
            if not isinstance(obs.gold, str) or not isinstance(obs.answer, str):
                raise ValueError("observations require nonmissing string gold/answer")
            signature[obs.logical_id, obs.group_id, obs.gold] += 1
            by_group[obs.group_id].append(obs)
        if reference is not None and signature != reference:
            raise ValueError("model observation gold/populations differ")
        reference, grouped[model] = signature, by_group
    groups = {group for rows in grouped.values() for group in rows}

    def evaluate(sample):
        result = {}
        for model, rows in grouped.items():
            selected = [obs for group in sample for obs in rows[group]]
            result[model] = macro_f1([o.gold for o in selected], [o.answer for o in selected]).macro_f1
        return result

    result = _bootstrap(per_model_obs, groups, evaluate, seed, set_name, reps)
    result["question_id"] = question_id
    return result
