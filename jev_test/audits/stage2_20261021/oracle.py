"""무엇: 독립 선택 지표 oracle · 입력: 요청 관측/가정 · 출력: 전수 대조 통계 · 계약 §9 C3."""

from fractions import Fraction
import math

from scipy.stats import binom


def selective(rows):
    """각 cutoff를 전수 검사하며 AUROC는 정답×오류 쌍을 직접 센다."""
    valid = [r for r in rows if r.valid and not r.mask_empty]
    denom = sum(not r.mask_empty for r in rows)
    points = []
    for cutoff in sorted({r.s for r in valid}, reverse=True):
        accepted = [r for r in valid if r.s >= cutoff]
        points.append((len(accepted), sum(r.wrong for r in accepted)))
    grid = []
    for tenth in range(1, 11):
        choices = [(n, k) for n, k in points if Fraction(n, denom) <= Fraction(tenth, 10)]
        n, k = max(choices, default=(0, 0))
        grid.append(dict(target=tenth/10, n_accepted=n if valid else None,
                         k_errors=k if valid else None, coverage=n/denom if valid else None,
                         risk=k/n if n else None))
    area, previous = Fraction(0), 0
    for n, k in points:
        area += Fraction(n-previous, denom) * Fraction(k, n)
        previous = n
    correct, errors = [r for r in valid if not r.wrong], [r for r in valid if r.wrong]
    wins = sum(2 if a.s > b.s else 1 if a.s == b.s else 0 for a in correct for b in errors)
    return dict(n_denom=denom, n_valid=len(valid),
        n_invalid=sum(not r.valid and not r.mask_empty for r in rows), grid=grid,
        partial_aurc=float(area) if valid else None, max_coverage=len(valid)/denom if valid else None,
        auroc=wins/(2*len(correct)*len(errors)) if correct and errors else None)


def passing_errors(n, tau):
    """CP 상한을 호출하지 않고 이항 하위꼬리 <= .05인 k를 전수 검사한다."""
    if n is None or n == 0:
        return None
    passing = [k for k in range(n+1) if binom.cdf(k, n, float(tau)) <= .05]
    return max(passing) if passing else None


def pass_probability(n, tau, r):
    """CDF 대신 각 오류 수의 PMF 합으로 통과 확률을 계산한다."""
    if n is None:
        return None
    maximum = passing_errors(n, tau)
    return 0. if maximum is None else math.fsum(float(binom.pmf(k, n, r)) for k in range(maximum+1))


def power(risk):
    return {tau: [dict(r=float(tau)*i/4,
        probability=pass_probability(risk['cells'][tau]['test']['n_accepted'], tau, float(tau)*i/4))
        for i in (1, 2, 3)] for tau in ('0.01', '0.02', '0.05')}


def differences(expected, actual, path=()):
    """정수·null·키·격자는 정확히, 실수 통계만 절대 오차로 비교한다."""
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or expected.keys() != actual.keys():
            return ['.'.join(path)]
        return [p for k in expected for p in differences(expected[k], actual[k], (*path, str(k)))]
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(expected) != len(actual):
            return ['.'.join(path)]
        return [p for i, v in enumerate(expected) for p in differences(v, actual[i], (*path, str(i)))]
    exact = 'grid' in path or type(expected) is not float
    equal = (type(expected) is type(actual) and expected == actual) if exact else (
        type(actual) in (float, int) and math.isfinite(actual) and abs(expected-actual) <= 1e-12)
    return [] if equal else ['.'.join(path)]
