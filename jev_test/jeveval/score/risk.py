"""무엇: CP 위험 인증 · 입력: 임계값·dev/test outcome·Item · 출력: RiskCell/파일 dict · 계약 §7-4."""

from fractions import Fraction
from functools import lru_cache

from scipy.stats import beta

from jeveval.score.risk_mix import distributions
from jeveval.score.threshold import TAUS, UNIT
from jeveval.types import Item, RequestOutcome, RiskCell, Threshold


def upper(k: int, n: int) -> float | None:
    """단측 Clopper–Pearson 95% 상한. 경계 판정 순서는 계획 §4-2 그대로다."""
    if type(k) is not int or type(n) is not int or not 0 <= k <= n:
        raise ValueError("expected integers 0 <= k <= n")
    if n == 0:
        return None
    if k == n:
        return 1.0
    if k == 0:
        return 1 - 0.05 ** (1 / n)
    return float(beta.ppf(0.95, k + 1, n - k))


def _tau(tau):
    if tau not in TAUS:
        raise ValueError("tau must be one of TAUS")
    return Fraction(tau)


@lru_cache(maxsize=3)
def n_min(tau: str) -> int:
    """U(0,n) <= tau와 동치인 (1-tau)**n <= 0.05를 정확한 유리수로 비교한다."""
    remaining, power, n = 1 - _tau(tau), Fraction(1), 0
    while power > Fraction(1, 20):
        n += 1
        power *= remaining
    return n


def b_flip(k: int, n: int, tau: str) -> int:
    """정답을 오류로 바꿔 상한을 넘는 최소 수. 바꿀 정답이 없으면 ValueError다."""
    upper(k, n)
    target = _tau(tau)
    if k == n:
        raise ValueError("no correct accepted request to flip")
    lo, hi = 1, n - k
    while lo < hi:
        mid = (lo + hi) // 2
        if upper(k + mid, n) > target:
            hi = mid
        else:
            lo = mid + 1
    return lo


def _accepted(rows, t):
    return [r for r in rows if t is not None and r.valid and not r.mask_empty and r.s >= t]


def _counts(rows, t):
    accepted = _accepted(rows, t)
    empty = sum(r.mask_empty for r in rows)
    return dict(n_groups=len(rows), n_denom=len(rows) - empty, n_empty_mask=empty,
                n_accepted=None if t is None else len(accepted),
                k_errors=None if t is None else sum(int(r.wrong) for r in accepted))


def _check_rows(rows, stage):
    if any(r.stage != stage for r in rows):
        raise ValueError(f"expected {stage} outcomes")
    if len({r.logical_id for r in rows}) != len(rows) or len({r.group_id for r in rows}) != len(rows):
        raise ValueError("expected unique group representatives")


def cell_status(tau, t_star, n, u):
    """요청/질문 지표가 동일한 CP 상태 경계를 공유한다. 표시 반올림은 하지 않는다."""
    target = _tau(tau)
    return ("NO_THRESHOLD" if t_star is None else "UNDERPOWERED" if n < n_min(tau)
            else "MEETS" if u <= target else "FAILS")


def risk_cell(*, tau: str, threshold: Threshold, dev: list[RequestOutcome],
              test: list[RequestOutcome], test_items: dict[str, Item], family_name=None) -> RiskCell:
    """봉인 임계값을 적용한다. 호출자는 분할의 대표 집합과 입력 완료를 먼저 대조한다."""
    target, minimum = _tau(tau), n_min(tau)
    if threshold.tau != tau or threshold.status not in ("SELECTED", "NO_THRESHOLD"):
        raise ValueError("threshold tau/status mismatch")
    if (threshold.status == "NO_THRESHOLD") != (threshold.t_star is None):
        raise ValueError("threshold status/t_star mismatch")
    _check_rows(dev, "dev")
    _check_rows(test, "test")
    for row in test:
        item = test_items[row.logical_id]
        if row.logical_id != f"{item.set}:{item.group_id}:{item.item_id}":
            raise ValueError("test outcome/Item logical_id mismatch")
    t = threshold.t_star
    development, trial = _counts(dev, t), _counts(test, t)
    if (development["n_accepted"] != threshold.n_accepted
            or development["k_errors"] != threshold.k_errors
            or threshold.coverage != dict(num=development["n_accepted"] or 0, den=development["n_denom"])):
        raise ValueError("threshold/dev counts mismatch")
    n, k = trial["n_accepted"], trial["k_errors"]
    u = None if t is None else upper(k, n)
    status = cell_status(tau, t, n, u)
    trial.update(U=u, coverage=dict(num=n or 0, den=trial["n_denom"]),
                 b_flip=b_flip(k, n, tau) if status == "MEETS" else None)
    by_status = {s: sum(r.status == s and not r.mask_empty for r in test)
                 for s in ("ok", "rejected", "truncated", "error")}
    accepted_ids = {r.logical_id for r in _accepted(test, t)}
    mix, lengths, diagnostic = distributions(test, test_items, accepted_ids, family_name)
    return RiskCell(tau, status, len(test) < minimum, UNIT, t, development, trial,
                    by_status, mix, lengths, diagnostic)


def risk_file(*, model, set, variant, run_id, threshold_sha256, cells) -> dict:
    """RiskCell을 중첩 dataclass 없는 risk/1 JSON 객체로 조립한다."""
    if cells.keys() != {*TAUS} or any(key != value.tau for key, value in cells.items()):
        raise ValueError("risk cells must contain matching TAUS")
    return dict(schema="risk/1", model=model, set=set, variant=variant, run_id=run_id,
                threshold_sha256=threshold_sha256, cells={k: v.to_dict() for k, v in cells.items()})
