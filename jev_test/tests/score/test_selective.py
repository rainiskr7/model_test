"""무엇: 선택적 통계 경계 · 입력: 합성 대표 · 출력: 동점/분모/적분 · 계약 §7-4c."""

from dataclasses import replace
import pytest

from jeveval.score.selective import statistics, risk_coverage_points
from tests.score.test_risk import row


def test_ties_grid_and_partial_area():
    rows = [row(0, 'test', s=.9), row(1, 'test', s=.9, wrong=True), row(2, 'test', s=.1)]
    rows += [row(3, 'test', valid=False, s=None, wrong=None), row(4, 'test', mask_empty=True)]
    value = statistics(rows)
    assert risk_coverage_points(rows) == [(2, 1), (3, 1)]
    assert value['n_denom'] == 4 and value['n_invalid'] == 1
    assert value['grid'][0] == dict(target=.1, n_accepted=0, k_errors=0, coverage=0., risk=None)
    assert value['grid'][4]['coverage'] == .5 and value['grid'][-1]['coverage'] == .75
    assert value['partial_aurc'] == pytest.approx(1 / 3)
    assert value['auroc'] == .25
    assert statistics(list(reversed(rows))) == value


@pytest.mark.parametrize('rows', [[], [row(0, 'test', valid=False, s=None, wrong=None)],
                                  [row(0, 'test', mask_empty=True)]])
def test_undefined_statistics(rows):
    value = statistics(rows)
    assert value['partial_aurc'] is value['max_coverage'] is value['auroc'] is None
    assert all(c['coverage'] is c['risk'] is c['n_accepted'] is None for c in value['grid'])


@pytest.mark.parametrize('wrong', [False, True])
def test_single_class_and_first_bundle_exceeds_grid(wrong):
    value = statistics([row(i, 'test', wrong=wrong) for i in range(3)])
    assert value['auroc'] is None and value['partial_aurc'] == int(wrong)
    assert all(c['coverage'] == 0 for c in value['grid'][:-1])


def test_representative_validation():
    r = row(0, 'test')
    for rows in ([r, r], [replace(r, stage='dev')], [replace(r, s=float('nan'))]):
        with pytest.raises(ValueError): statistics(rows)
