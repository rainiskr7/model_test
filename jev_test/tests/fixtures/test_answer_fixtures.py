"""무엇: 답·칸 fixture 검산 · 입력: 합성 응답 · 출력: 규칙 대조 · 계약 §3-2·§7-2·§9."""

from collections import Counter
import json
import math

import pytest

from jeveval.types import ParsedAnswer
from test_fixtures_wellformed import ROOT, read


def test_systemone_answers():
    for case in read(ROOT / 'answers/systemone.json')['cases']:
        raw, expected = case['raw'], case['expected']
        if raw['type'] == 'noul':
            p = raw['noul']
            answer, probs, confidence = 'true' if p >= .5 else 'false', {'true':p, 'false':1-p}, max(p, 1-p)
        else:
            answer, probs, confidence = raw['choice'], raw['probabilities'], raw['confidence']
        parsed = ParsedAnswer(type=raw['type'], answer=answer, probs=probs, confidence=confidence)
        assert parsed.to_dict() == expected['parsed']
        warnings = ['choice_not_argmax'] if raw['type'] == 'choice' and probs[answer] < max(probs.values())-1e-9 else []
        assert warnings == expected['warnings']


def test_b1_distribution_and_swapped_noul_tie():
    cases = read(ROOT / 'b1/renormalization.json')['cases']
    for case in cases:
        logs = {r['token']: r['logprob'] for r in case['top_logprobs']}
        labels = case['label_order']
        maximum = max(logs[label] for label in labels)
        weights = {label: math.exp(logs[label]-maximum) for label in labels}
        probs = {label: w/sum(weights.values()) for label, w in weights.items()}
        assert probs == pytest.approx(case['expected']['label_probabilities'])
        true_label = next(label for label in labels if case['label_map'][label] == 'true')
        p = probs[true_label]
        parsed = case['expected']['parsed']
        assert parsed['answer'] == ('true' if p >= .5 else 'false')
        assert parsed['probs'] == pytest.approx({'true':p, 'false':1-p})
        assert parsed['confidence'] == pytest.approx(max(p, 1-p))
    tie = next(c for c in cases if c['name'] == 'swapped_tie')
    assert tie['label_map']['A'] == 'false' and tie['expected']['parsed']['answer'] == 'true'


def test_b1_missing_labels():
    fixture = read(ROOT / 'b1/missing_label.json')
    for case in fixture['cases']:
        rows = case.get('top_logprobs') or json.loads(case['top_logprobs_raw'])
        logs = {r['token']:r['logprob'] for r in rows}
        assert any(label not in logs or not math.isfinite(logs[label]) or logs[label] <= -9999
                   for label in fixture['label_map'])
        assert fixture['expected'] == {'status':'error', 'reason':'b1_missing_label'}


def test_kosgd_fixed_slots_and_previous():
    fixture = read(ROOT / 'scoring/kosgd_slots.json')
    for case in fixture['cases']:
        fixed = sorted(case['gold_intents'], key=fixture['catalog_order'].index)
        fixed += ['NONE']*(2-len(fixed))
        prediction = case['predicted']
        duplicate = any(n > 1 and value != 'NONE' for value, n in Counter(prediction).items())
        correct = Counter(fixed) == Counter(prediction) and not duplicate
        expected = case['expected']
        assert expected['fixed_gold'] == fixed
        assert expected['group_correct'] == correct
        assert expected['duplicate_non_none'] == duplicate
        assert expected['order_only'] == (correct and fixed != prediction)
        if 'copy_prev' in case:
            assert expected['copy_prev_correct'] == (Counter(case['copy_prev']) == Counter(fixed))
    c = fixture['counterexample']
    briers = [sum((p-(key==gold))**2 for key,p in probs.items())
              for gold,probs in zip(c['fixed_gold'],c['probabilities'])]
    assert briers == pytest.approx(c['expected']['fixed_slot_brier'])
    assert sum(briers)/2 == pytest.approx(c['expected']['fixed_mean_brier'])
