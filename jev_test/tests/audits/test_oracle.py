"""무엇: 독립 oracle 대조 · 입력: 무효/동점/경계 · 출력: 구현과 1e-12 일치 · 계약 §9 C3."""

import ast
from pathlib import Path
import pytest
from audits.stage2_20261021 import oracle
from jeveval.score.selective import statistics
from jeveval.score.power import conditional_pass_probability
from jeveval.score.risk import n_min
from tests.score.test_risk import row


@pytest.mark.parametrize('rows', [[], [row(0, 'test', valid=False, s=None, wrong=None)],
    [row(i, 'test', wrong=True) for i in range(3)], [row(i, 'test') for i in range(3)],
    [row(i, 'test', s=(i%3)/3, wrong=i%2 == 0) for i in range(19)]])
def test_selective_oracle(rows):
    assert oracle.differences(oracle.selective(rows), statistics(rows)) == []


@pytest.mark.parametrize('tau', ['0.01', '0.02', '0.05'])
def test_power_binomial_duality_and_pmf_sum(tau):
    for n in (None, 0, n_min(tau)-1, n_min(tau), n_min(tau)*3):
        for fraction in (1, 2, 3):
            r = float(tau)*fraction/4
            assert oracle.differences(oracle.pass_probability(n, tau, r), conditional_pass_probability(n, tau, r)) == []


def test_oracle_has_no_production_import_and_exact_integer_comparison():
    tree = ast.parse(Path(oracle.__file__).read_text())
    assert not any(isinstance(n, ast.ImportFrom) and (n.module or '').startswith('jeveval') for n in ast.walk(tree))
    assert oracle.differences({'n': 1}, {'n': 1.0})
    assert oracle.differences({'risk': .5}, {'risk': .5+1e-10})


def test_partial_coverage_and_empty_mask_oracle():
    rows = [row(0, 'test', s=.9), row(1, 'test', s=.9, wrong=True), row(2, 'test', s=.1),
            row(3, 'test', valid=False, s=None, wrong=None), row(4, 'test', mask_empty=True)]
    value = oracle.selective(rows)
    assert value['max_coverage'] == .75 and value['grid'][0]['risk'] is None
    assert oracle.differences(value, statistics(rows)) == []
