"""무엇: 후보 선택 경계 · 입력: dev 후보 · 출력: 고정 동점/NO_THRESHOLD · 계약 §7-4d."""

from dataclasses import replace
import pytest
from jeveval.score.variant_selection import select_variant_by_tau
from jeveval.score.variant_scores import CANDIDATES
from tests.score.test_risk import row


def test_candidate_order_and_no_threshold():
    for rows in ([], [row(0, wrong=True)], [row(0)]):
        selected = select_variant_by_tau({n: rows for n in CANDIDATES})
        assert all(c['candidate'] == 'min' for c in selected.values())
    assert select_variant_by_tau({n: [] for n in CANDIDATES})['0.02']['threshold']['status'] == 'NO_THRESHOLD'


def test_more_accepted_wins_and_test_never_selects():
    bad = [row(0, s=.5), row(1, s=.5, wrong=True)]
    good = [row(0, s=.9), row(1, s=.1, wrong=True)]
    candidates = {n: good if n == 'product' else bad for n in CANDIDATES}
    assert select_variant_by_tau(candidates)['0.02']['candidate'] == 'product'
    candidates['min'] = [replace(r, stage='test') for r in bad]
    with pytest.raises(ValueError): select_variant_by_tau(candidates)
