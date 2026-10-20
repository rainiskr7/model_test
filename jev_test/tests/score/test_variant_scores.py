"""무엇: 후보 단위 의미 · 입력: 성공/결측/칸 묶음 · 출력: min 동일/곱 · 계약 §7-4d."""

from dataclasses import replace
from jeveval.score.question_outcomes import observations
from jeveval.score.variant_scores import candidate_scores
from tests.score.population_support import question, answer, record


def test_missing_success_and_diagnostic_and_unseen_identity():
    qs = [question('a'), question('missing', gold=None), question('diag', role='diagnostic')]
    item, final, row = record(qs, dict(a=answer(confidence=.8), missing=answer(confidence=.2), diag=answer(confidence=.01)))
    units = observations([final], {row.logical_id: item}, 'test')
    result = candidate_scores([row], units, {})
    assert result['min'][0] == row and result['product'][0].s == .8*.2
    assert result['iso_min'] == result['min'] and result['iso_product'] == result['product']
    changed = [replace(u, gold='false', wrong=True) for u in units]
    assert candidate_scores([row], changed, {}) == result


def test_slots_use_one_min_bundle_before_product():
    opts = {'a': 'a', 'NONE': 'none'}
    qs = [question('x', 'a', 'ongoing_slot_1', opts), question('y', 'NONE', 'ongoing_slot_2', opts)]
    item, final, row = record(qs, dict(x=answer('a', {'a': .8, 'NONE': .2}, .8),
                                    y=answer('NONE', {'a': .2, 'NONE': .8}, .2)))
    units = observations([final], {row.logical_id: item}, 'test')
    assert len(units) == 1
    result = candidate_scores([row], units, {})
    assert result['min'][0].s == result['product'][0].s == .2
