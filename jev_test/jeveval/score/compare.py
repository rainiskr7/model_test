"""무엇: 모델 횡단 비교 · 입력: 모델별 식별자/코호트 · 출력: 오류/compare/1 · 계약 §7-6·§8-6 L."""

from builtins import set as builtins_set
from copy import deepcopy
from hashlib import sha256

from jeveval.types import RequestOutcome


def check_comparable(models: dict[str, dict]) -> list[str]:
    errors, reference = [], None
    for model in sorted(models):
        data = models[model]
        fields = ("split_sha256", "task_sha256", "test_logical_ids")
        if any(k not in data for k in fields):
            errors.append(f"{model}: missing comparison fields")
            continue
        ids = data["test_logical_ids"]
        if len(ids) != len(set(ids)):
            errors.append(f"{model}: duplicate test logical_id")
        current = (data["split_sha256"], data["task_sha256"], set(ids))
        if reference is None:
            reference = current
        else:
            errors.extend(f"{model}: {key} differs" for key, a, b in zip(fields, reference, current) if a != b)
    if len(models) < 2:
        errors.append("comparison requires at least two models")
    return errors


def common_cohort(per_model_outcomes: dict[str, list[RequestOutcome]], stage_filter="test") -> list[str]:
    """test 또는 all_rows(dev+test+extra)의 정확한 모든 모델 ok 교집합."""
    if stage_filter not in ("test", "all_rows"):
        raise ValueError("stage_filter must be test or all_rows")
    cohorts = []
    for rows in per_model_outcomes.values():
        if len({r.logical_id for r in rows}) != len(rows):
            raise ValueError("duplicate logical_id")
        if any(r.stage not in ("dev", "test", "extra") for r in rows):
            raise ValueError("invalid outcome stage")
        cohorts.append({r.logical_id for r in rows if r.status == "ok"
                        and (stage_filter == "all_rows" or r.stage == "test")})
    return sorted(set.intersection(*cohorts)) if cohorts else []


def compare_file(*, models, set, variant, cohort_ids, per_model_population, bootstrap) -> dict:
    """호출자는 C4 검사 뒤 정확한 공통 코호트의 Population을 전달한다."""
    names, ids = sorted(models), sorted(cohort_ids)
    if len(names) != len(builtins_set(names)) or builtins_set(names) != per_model_population.keys():
        raise ValueError("comparison model keys differ or duplicate")
    if len(ids) != len(builtins_set(ids)):
        raise ValueError("duplicate cohort logical_id")
    for pop in per_model_population.values():
        if pop.counts["n_sampled"] != len(ids) or pop.counts["by_status"]["ok"] != len(ids):
            raise ValueError("population differs from common ok cohort")
    return dict(schema="compare/1", models=names, set=set, variant=variant,
                common_cohort=dict(n=len(ids), logical_ids_sha256=sha256("\n".join(ids).encode()).hexdigest(),
                                   per_model={m: per_model_population[m].to_dict() for m in names}),
                bootstrap=deepcopy(bootstrap))
