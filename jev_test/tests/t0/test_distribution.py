"""T0 분포 벡터 순서 및 수치 경계."""

import pytest

from jeveval.t0.distribution import nonnegative, vector, within


@pytest.mark.parametrize("value,expected", [(0, True), (.1, True), (-.1, False), (True, False),
    (None, False), ("0", False), (float("nan"), False), (float("inf"), False), (10 ** 1000, False)])
def test_nonnegative_finite_numeric_domain(value, expected):
    assert nonnegative(value) is expected


def test_within_respects_exact_zero_and_float_boundary():
    assert within(0, 0) and not within(1e-30, 0)
    assert within(.3 - .1, .2)
    assert not within(.200001, .2)


@pytest.mark.parametrize("question,answer,expected", [
    ({"type": "noul"}, {"noul": .25}, [.25, .75]),
    ({"type": "choice", "criteria": {"Z": "z", "A": "a"}},
     {"probabilities": {"Z": .2, "A": .7}}, [.7, .2]),
    ({"type": "score", "criteria": ["zero", "one", "two"]},
     {"probabilities": {"2": .4, "0": .1, "1": .3}}, [.1, .3, .4])])
def test_vector_order_without_renormalizing(question, answer, expected):
    assert vector(question, answer) == expected
