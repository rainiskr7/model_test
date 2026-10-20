"""무엇: 조건부 검정력 경계 · 입력: n/τ/r · 출력: 이항 oracle 일치 · 계약 §7-4c."""

import pytest
from scipy.stats import binom
from jeveval.score.power import max_passing_errors, conditional_pass_probability
from jeveval.score.risk import n_min, upper


@pytest.mark.parametrize('tau', ['0.01', '0.02', '0.05'])
def test_power_boundaries_and_exhaustive_errors(tau):
    for n in (0, n_min(tau)-1, n_min(tau), n_min(tau)*2):
        possible = [k for k in range(n+1) if upper(k, n) is not None and upper(k, n) <= float(tau)]
        expected = max(possible) if possible else None
        assert max_passing_errors(n, tau) == expected
        for r in (0., float(tau)/4, float(tau)/2, 3*float(tau)/4, 1.):
            actual = conditional_pass_probability(n, tau, r)
            assert actual == pytest.approx(0 if expected is None else binom.cdf(expected, n, r), abs=1e-12)
    assert conditional_pass_probability(None, tau, .1) is None


@pytest.mark.parametrize('n,tau,r', [(-1, '0.02', .1), (True, '0.02', .1), (1, 'x', .1), (1, '0.02', float('nan'))])
def test_bad_inputs(n, tau, r):
    with pytest.raises(ValueError): conditional_pass_probability(n, tau, r)
