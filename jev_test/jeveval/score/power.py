"""무엇: 조건부 CP 통과 확률 · 입력: 관측 n/τ/가정 위험 · 출력: 확률 · 계약 §7-4c."""

import math
from fractions import Fraction

from scipy.stats import binom

from jeveval.score.risk import upper
from jeveval.score.threshold import TAUS


def max_passing_errors(n, tau):
    """U(k,n) 경계의 마지막 정수를 이분 탐색한다."""
    if tau not in TAUS or (n is not None and (type(n) is not int or n < 0)):
        raise ValueError("invalid power input")
    if n is None or n == 0 or upper(0, n) > Fraction(tau):
        return None
    lo, hi = 0, n
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if upper(mid, n) <= Fraction(tau):
            lo = mid
        else:
            hi = mid - 1
    return lo


def conditional_pass_probability(n, tau, r):
    """NO_THRESHOLD는 null, 고정 n에서 통과 불가능하면 0이다."""
    if type(r) not in (int, float) or not math.isfinite(r) or not 0 <= r <= 1:
        raise ValueError("invalid assumed risk")
    maximum = max_passing_errors(n, tau)
    if n is None:
        return None
    return 0.0 if maximum is None else float(binom.cdf(maximum, n, r))


def power_table(risk):
    """옛 risk/1에서도 test 수락 수만으로 계산한다."""
    return {tau: [dict(r=float(tau) * fraction / 4,
                      probability=conditional_pass_probability(
                          risk["cells"][tau]["test"]["n_accepted"], tau, float(tau) * fraction / 4))
                  for fraction in (1, 2, 3)] for tau in TAUS}
