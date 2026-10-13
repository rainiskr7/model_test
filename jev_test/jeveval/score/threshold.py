"""무엇: 개발 임계값·완료 대조 · 입력: RequestOutcome·SplitPlan · 출력: Threshold/File·오류 · 계약 §7-5·§8-6 E."""

from collections import Counter
from fractions import Fraction
from itertools import groupby

from jeveval.types import RequestOutcome, SplitPlan, Threshold, ThresholdFile


TAUS = ("0.01", "0.02", "0.05")
RULE = "plan-4-2:dev_risk<=tau/2;max_coverage;tie_larger_t"
UNIT = "group_representative"


def select(dev: list[RequestOutcome], tau: str) -> Threshold:
    """같은 확신은 묶어서 수락하며 위험 경계는 정확한 유리수로 비교한다."""
    if tau not in TAUS:
        raise ValueError("tau must be one of TAUS")
    target = Fraction(tau)
    n_denom = sum(not row.mask_empty for row in dev)
    eligible = sorted((row for row in dev if row.valid and not row.mask_empty),
                      key=lambda row: row.s, reverse=True)
    selected = None
    n = k = 0
    for t, tied in groupby(eligible, key=lambda row: row.s):
        for row in tied:
            n += 1
            k += row.wrong
        if 2 * k <= target * n:
            if selected is None or (n, t) > (selected.n_accepted, selected.t_star):
                selected = Threshold(tau, "SELECTED", t, n, k, {"num": n, "den": n_denom})
    return selected if selected is not None else Threshold(
        tau, "NO_THRESHOLD", None, None, None, {"num": 0, "den": n_denom})


def dev_complete(dev_logical_ids: list[str], plan: SplitPlan) -> list[str]:
    """dev 묶음의 대표 logical_id와 대조하여 누락·남는 것·중복을 모두 돌려준다."""
    expected = {plan.representative[group_id] for group_id in plan.dev}
    counts = Counter(dev_logical_ids)
    actual = set(counts)
    errors = [f"missing dev logical_id: {qid}" for qid in sorted(expected - actual)]
    errors += [f"unexpected dev logical_id: {qid}" for qid in sorted(actual - expected)]
    errors += [f"duplicate dev logical_id: {qid}" for qid in sorted(counts) if counts[qid] > 1]
    return errors


def threshold_file(*, model, set, variant, run_id, dev_sha256, dev_nbytes,
                   dev: list[RequestOutcome]) -> ThresholdFile:
    """호출자가 완료 대조한 dev 결과와 원본 바이트 식별자로 봉인 대상 값을 만든다."""
    if any(row.stage != "dev" for row in dev):
        raise ValueError("threshold input must contain only dev outcomes")
    n_empty = sum(row.mask_empty for row in dev)
    dev_input = dict(path="dev/final.jsonl", sha256=dev_sha256, nbytes=dev_nbytes,
                     n_groups=len(dev), n_denom=len(dev) - n_empty, n_empty_mask=n_empty)
    return ThresholdFile(schema="threshold/1", model=model, set=set, variant=variant,
                         run_id=run_id, rule=RULE, unit=UNIT, dev_input=dev_input,
                         by_tau={tau: select(dev, tau) for tau in TAUS})
