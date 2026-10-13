"""무엇: 채점 fixture 독립 검산 · 입력: 합성 JSON · 출력: 검증 · 계약 §7·§9."""

from copy import deepcopy

import pytest

from reference_scoring import calibration_reference, f1_reference, threshold_reference
from test_fixtures_wellformed import ROOT, read
from jeveval.types import Threshold


def assert_calibration(actual, expected):
    for key in ('ece', 'brier', 'log_loss'):
        assert actual[key] == pytest.approx(expected[key]) if expected[key] is not None else actual[key] is None
    assert len(actual['bins']) == len(expected['bins']) == 15
    for a, b in zip(actual['bins'], expected['bins']):
        assert a == pytest.approx(b)


def test_thresholds_recomputed_from_dev_only():
    cases = read(ROOT / 'scoring/threshold_cases.json')['cases']
    for case in cases:
        before = deepcopy(case)
        for tau, expected in case['expected']['by_tau'].items():
            actual = threshold_reference(case['dev'], tau)
            assert actual == expected
            assert Threshold.from_dict(expected).tau == tau
        for test in case.get('test_variants', []):
            changed = dict(case, test=test)
            assert {tau: threshold_reference(changed['dev'], tau)
                    for tau in ('0.01', '0.02', '0.05')} == case['expected']['by_tau']
        assert case == before
    functionchat = next(c for c in cases if c['name'] == 'functionchat_dev_21_groups')
    assert len({r['group_id'] for r in functionchat['dev']}) == 21
    assert sum(r['member_count'] for r in functionchat['dev']) > 21
    assert all(t['coverage']['den'] == 21 for t in functionchat['expected']['by_tau'].values())


def test_calibration_bins_brier_and_clip():
    fixture = read(ROOT / 'scoring/calibration.json')
    for name, question in fixture['questions'].items():
        rows = question['observations']
        assert_calibration(calibration_reference(rows), question['expected'])
        assert sum(b['n'] for b in question['expected']['bins']) == len(rows)
        if name == 'noul':
            binary = sum(2*(r['probs']['true'] - (r['gold'] == 'true'))**2 for r in rows)/len(rows)
            assert binary == pytest.approx(question['expected']['brier'])


def test_f1_classes_and_zero_denominators():
    for case in read(ROOT / 'scoring/f1_classes.json')['cases']:
        classes, fs, macro = f1_reference(case['gold'], case['predicted'])
        expected = case['expected']
        assert classes == expected['class_stats']
        assert set(classes) == set(expected['classes'])
        assert fs == pytest.approx(expected['per_class_f1'])
        assert macro == expected['macro_f1']


def test_missing_masks_keep_low_confidence():
    fixture = read(ROOT / 'scoring/missing_mask.json')
    empty = 0
    for request in fixture['requests']:
        questions = request['questions']
        success = [q for q in questions if q['role'] == 'success']
        mask = [q for q in success if q['gold'] is not None]
        valid = request['status'] == 'ok'
        empty += not mask
        assert request['expected'] == dict(
            valid=valid, s=min(q['confidence'] for q in success) if valid else None,
            mask_empty=not mask,
            wrong=any(q['answer'] != q['gold'] for q in mask) if valid and mask else None,
            n_missing=sum(q['gold'] is None for q in questions) if valid else 0)
    assert fixture['expected'] == {'n_empty_mask':empty, 'n_denom':len(fixture['requests'])-empty}


def test_cohorts_populations_and_pooled_aspects():
    fixture = read(ROOT / 'scoring/cohort_population.json')
    cohorts = [{i for i, status in rows.items() if status == 'ok'}
               for rows in fixture['models'].values()]
    assert sorted(set.intersection(*cohorts)) == fixture['expected']['common_cohort']
    fc = fixture['functionchat']
    assert sorted(fc['dev']+fc['test']+fc['extra']) == sorted(i for group in fc['groups'].values() for i in group)
    assert len({len(group) for group in fc['groups'].values()}) > 1
    for name, members in [('test', fc['test']), ('all_rows', fc['dev']+fc['test']+fc['extra'])]:
        assert fixture['expected']['functionchat'][name] == dict(
            certified=name == 'test', unit='group_representative' if name == 'test' else 'row',
            n_sampled=len(members), n_scored=sum(fc['statuses'][i] == 'ok' for i in members))
    questions = fixture['korfin']['questions']
    pooled = [r for rows in questions.values() for r in rows]
    expected = fixture['expected']['korfin']
    macro = lambda rows: f1_reference([r['gold'] for r in rows], [r['answer'] for r in rows])[2]
    assert macro(pooled) == pytest.approx(expected['pooled']['macro_f1'])
    assert len(pooled) == expected['pooled']['n_scored']
    assert expected['pooled']['accuracy'] == {'num':sum(r['gold']==r['answer'] for r in pooled), 'den':len(pooled)}
    mean = sum(macro(rows) for rows in questions.values()) / len(questions)
    assert mean == expected['question_macro_f1_mean']
    assert macro(pooled) != mean
    assert_calibration(calibration_reference(pooled), expected['pooled']['calibration'])
