"""무엇: 동결 후보 test 적용 · 입력: 고정 정책/시험 · 출력: 주 CP 경계 동일 · 계약 §7-4d."""

from jeveval.score.variant_risk import apply_variant_policy
from jeveval.score.variant_selection import select_variant_by_tau
from jeveval.score.variant_scores import CANDIDATES
from tests.score.test_risk import row


def test_frozen_selection_survives_test_errors():
    selected = select_variant_by_tau({n: [row(0)] for n in CANDIDATES})
    candidates = {n: [row(i, 'test', wrong=True) for i in range(300)] for n in CANDIDATES}
    cells = apply_variant_policy(candidates, selected)
    assert all(c['candidate'] == 'min' and c['test']['status'] == 'FAILS' for c in cells.values())
    empty = select_variant_by_tau({n: [] for n in CANDIDATES})
    assert apply_variant_policy(candidates, empty)['0.02']['test']['n_accepted'] is None
