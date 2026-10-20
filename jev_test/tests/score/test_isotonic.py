"""무엇: 순수 PAV 검증 · 입력: 동점/역전/희소 · 출력: 가중 블록/계단 · 계약 §7-4d."""

import pytest
from jeveval.score.isotonic import fit_isotonic, apply_isotonic


def test_weighted_ties_and_adjacent_violators():
    fit = fit_isotonic([(.1, 1), (.1, 0), (.2, 0), (.3, 1)])
    assert fit == dict(x=[.1, .2, .3], y=[1/3, 1/3, 1.])
    assert [apply_isotonic(fit, x) for x in (0., .1, .19, .29, .3, 1.)] == [1/3]*4 + [1., 1.]
    assert fit == fit_isotonic([(.3, 1), (.2, 0), (.1, 0), (.1, 1)])


@pytest.mark.parametrize('pairs', [[], [(.2, 0)], [(.2, 1), (.7, 1)]])
def test_identity_fallback(pairs):
    fit = fit_isotonic(pairs)
    assert fit == dict(x=[], y=[]) and apply_isotonic(fit, .39) == .39


def test_invalid_inputs_and_knots():
    with pytest.raises(ValueError): fit_isotonic([(float('nan'), 0)])
    with pytest.raises(ValueError): apply_isotonic(dict(x=[.1, .1], y=[0., 1.]), .2)
