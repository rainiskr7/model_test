"""무엇: 동결 확신 정책 적용 · 입력: test 후보/선택 · 출력: τ별 CP 셀 · 계약 §7-4d."""

from jeveval.score.risk import cell_status, upper
from jeveval.score.threshold import TAUS


def apply_variant_policy(candidates, selected):
    """선택을 다시 하지 않고 test 점수에 동결 임계값만 적용한다."""
    result = {}
    if set(selected) != set(TAUS):
        raise ValueError("variant taus differ")
    for tau in TAUS:
        policy = selected[tau]
        rows = candidates[policy["candidate"]]
        if any(r.stage != "test" for r in rows) or len({r.group_id for r in rows}) != len(rows):
            raise ValueError("expected test representatives")
        t = policy["threshold"]["t_star"]
        accepted = [r for r in rows if t is not None and r.valid and not r.mask_empty and r.s >= t]
        n, k = (None, None) if t is None else (len(accepted), sum(int(r.wrong) for r in accepted))
        u = None if t is None else upper(k, n)
        result[tau] = dict(candidate=policy["candidate"], dev=policy["threshold"],
            test=dict(t_star=t, n_accepted=n, k_errors=k, U=u, status=cell_status(tau, t, n, u),
                      coverage=dict(num=n or 0, den=sum(not r.mask_empty for r in rows))))
    return result
