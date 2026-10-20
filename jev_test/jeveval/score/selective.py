"""무엇: 선택적 예측 통계 · 입력: test 대표 outcome · 출력: RC/부분 AURC/AUROC · 계약 §7-4c."""

from itertools import groupby
import math


def risk_coverage_points(rows):
    """같은 점수는 분리하지 않으며 무효·빈 마스크를 수락하지 않는다."""
    eligible = sorted((r for r in rows if r.valid and not r.mask_empty), key=lambda r: r.s, reverse=True)
    n = k = 0
    points = []
    for _, tied in groupby(eligible, key=lambda r: r.s):
        for row in tied:
            n += 1
            k += int(row.wrong)
        points.append((n, k))
    return points


def coverage_grid(points, denom):
    """격자 비교는 정수로 한다. 정의 불가와 도달 전 0 수락을 구별한다."""
    result = []
    for tenth in range(1, 11):
        chosen = [(n, k) for n, k in points if 10 * n <= tenth * denom]
        n, k = chosen[-1] if chosen else (0, 0)
        defined = bool(denom and points)
        result.append(dict(target=tenth / 10, n_accepted=n if defined else None,
                           k_errors=k if defined else None, coverage=n / denom if defined else None,
                           risk=k / n if defined and n else None))
    return result


def partial_aurc(points, denom):
    """도달 가능한 최대 처리율까지 우측 직사각형 적분한다."""
    if not denom or not points:
        return dict(partial_aurc=None, max_coverage=None)
    previous, terms = 0, []
    for n, k in points:
        terms.append((n - previous) / denom * k / n)
        previous = n
    return dict(partial_aurc=math.fsum(terms), max_coverage=points[-1][0] / denom)


def correctness_auroc(rows):
    """정답을 양성으로 하며 동점 쌍은 절반으로 센다."""
    eligible = sorted((r for r in rows if r.valid and not r.mask_empty), key=lambda r: r.s)
    positive = sum(not r.wrong for r in eligible)
    negative = len(eligible) - positive
    if not positive or not negative:
        return None
    lower_errors = twice_wins = 0
    for _, tied in groupby(eligible, key=lambda r: r.s):
        tied = list(tied)
        errors = sum(r.wrong for r in tied)
        correct = len(tied) - errors
        twice_wins += correct * (2 * lower_errors + errors)
        lower_errors += errors
    return twice_wins / (2 * positive * negative)


def statistics(rows):
    """정확한 대표 단위와 점수 범위를 검증한 집계만 공개한다."""
    if any(r.stage != "test" for r in rows) or len({r.group_id for r in rows}) != len(rows):
        raise ValueError("expected test representatives")
    if len({r.logical_id for r in rows}) != len(rows):
        raise ValueError("duplicate logical ID")
    eligible = [r for r in rows if r.valid and not r.mask_empty]
    if any(type(r.s) not in (float, int) or not math.isfinite(r.s) or not 0 <= r.s <= 1
           or type(r.wrong) is not bool for r in eligible):
        raise ValueError("invalid selective input")
    denom = sum(not r.mask_empty for r in rows)
    points = risk_coverage_points(rows)
    return dict(n_denom=denom, n_valid=len(eligible),
                n_invalid=sum(not r.valid and not r.mask_empty for r in rows),
                grid=coverage_grid(points, denom), auroc=correctness_auroc(rows), **partial_aurc(points, denom))
