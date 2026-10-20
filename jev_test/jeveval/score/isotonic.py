"""무엇: PAV 단조 보정 · 입력: 점수/정오 관측 · 출력: 계단 보정기/점수 · 계약 §7-4d."""

from bisect import bisect_right
from itertools import groupby
import math


def fit_isotonic(pairs):
    """동일 x를 먼저 묶고 역전된 인접 블록을 가중 평균으로 합친다."""
    pairs = list(pairs)
    if any(type(x) not in (int, float) or not math.isfinite(x) or not 0 <= x <= 1
           or type(y) not in (bool, int) or y not in (0, 1) for x, y in pairs):
        raise ValueError("invalid isotonic observations")
    if len({y for _, y in pairs}) < 2:
        return dict(x=[], y=[])
    blocks, xs = [], []
    for x, group in groupby(sorted(pairs), key=lambda p: p[0]):
        ys = [y for _, y in group]
        xs.append(x)
        blocks.append([len(xs) - 1, len(xs), sum(ys), len(ys)])
        while len(blocks) > 1 and blocks[-2][2] * blocks[-1][3] > blocks[-1][2] * blocks[-2][3]:
            right, left = blocks.pop(), blocks.pop()
            blocks.append([left[0], right[1], left[2] + right[2], left[3] + right[3]])
    values = [0.] * len(xs)
    for start, end, total, weight in blocks:
        values[start:end] = [total / weight] * (end - start)
    return dict(x=xs, y=values)


def apply_isotonic(fitted, score):
    """항등 fallback 또는 좌측 학습점 계단을 적용하고 양 끝을 고정한다."""
    if type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 1:
        raise ValueError("invalid confidence")
    xs, ys = fitted["x"], fitted["y"]
    if len(xs) != len(ys) or any(a >= b for a, b in zip(xs, xs[1:])):
        raise ValueError("invalid isotonic knots")
    if any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in xs + ys):
        raise ValueError("invalid isotonic values")
    if any(a > b for a, b in zip(ys, ys[1:])):
        raise ValueError("nonmonotone isotonic values")
    return score if not xs else ys[max(0, bisect_right(xs, score) - 1)]
