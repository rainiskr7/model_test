"""무엇: 기록·길이·펼치기 fixture 대조 · 입력: 합성 JSON · 출력: 검증 · 계약 §1·§4·§5·§6·§9."""

from copy import deepcopy
import json

from jeveval.contract.taskspec import validate_taskspec
from jeveval.types import BoundQuestion, FinalRecord, LengthInfo, ParsedAnswer, TaskSpec
from test_fixtures_wellformed import ROOT, read


def test_record_states_and_nested_restoration():
    cases = read(ROOT / 'records/roundtrip.json')['cases']
    assert {c['name'] for c in cases} == {'ok','truncated','rejected','invalid','b1_partial'}
    for case in cases:
        source = case['record']
        record = FinalRecord.from_dict(source)
        assert FinalRecord.from_dict(json.loads(json.dumps(record.to_dict()))) == record
        assert (record.status == 'ok') == case['expected']['scorable']
        assert sum(c.answers_parsed is not None for c in record.calls) == case['expected']['parsed_call_count']
        for call in record.calls:
            assert isinstance(call.length, LengthInfo)
            if call.status in ('ok','truncated'):
                assert call.answers_parsed and all(isinstance(a, ParsedAnswer) for a in call.answers_parsed.values())
            else:
                assert call.answers_parsed is None
        record.calls[0].warnings.append('detached')
        assert source['calls'][0]['warnings'] == []


def test_korfin_expansion_contract_data():
    f = read(ROOT / 'expand/korfin.json')
    assert isinstance(validate_taskspec(f['task']), TaskSpec)
    assert len(f['rows']) == len(f['expected']['questions'])
    assert len({row['SRC'] for row in f['rows']}) == 1
    assert min(row['SID'] for row in f['rows']).split('_')[0] == f['expected']['group_id']
    pattern = f['task']['per_item_questions']
    for i, (row, expected) in enumerate(zip(f['rows'],f['expected']['questions']), 1):
        q = BoundQuestion.from_dict(expected)
        assert q.id == pattern['id_pattern'].replace('{k}',str(i))
        assert q.instructions == pattern['instructions_template'].replace('{ASPECT}',row['ASPECT'])
        assert q.gold == row['gold'] and q.options == f['options']
    for qid in f['collision_ids'] + f['noncollision_ids']:
        task = deepcopy(f['task'])
        task['questions'] = [dict(id=qid, role='diagnostic', type='choice',
                                  instructions='골라요.', options='sentiment', label='static')]
        result = validate_taskspec(task)
        assert isinstance(result, list) == (qid in f['collision_ids'])


def test_length_classification_and_state_priority():
    fixture = read(ROOT / 'length/boundaries.json')
    for c in fixture['cases']:
        i, expected = c['input'], c['expected']
        cut = i['length_tokens'] > i['limit']
        reason = ('target_cut' if i['target_end'] > i['limit']-i['fixed_tokens'] else 'tail_cut') if cut else None
        status = 'truncated' if cut else 'ok'
        if i['matches_confirmed_input_limit_response']:
            status, reason = 'rejected', 'input_limit'
        assert (status, reason) == (expected['status'],expected['reason'])
        assert expected['answered_over_limit'] == (cut and i['validated_response'] and status != 'rejected')
        warnings = ['length_mismatch'] if not cut and i['usage_input_tokens'] != i['length_tokens'] else []
        assert expected['warnings'] == warnings
    b1 = fixture['b1_logical']
    actual = [('not_truncated' if c['length_tokens'] <= c['limit'] else
               'target_cut' if c['target_end'] > c['limit']-c['fixed_tokens'] else 'tail_cut') for c in b1['calls']]
    assert actual == b1['expected']['classifications']
    assert max(c['length_tokens'] for c in b1['calls']) == b1['expected']['length_max']


def test_terminal_recovery_expected_record():
    fixture = read(ROOT / 'resume/terminal_recovery.json')
    attempt = json.loads(fixture['attempts_jsonl'])
    final = FinalRecord.from_dict(fixture['expected']['final'])
    assert attempt['terminal'] and fixture['expected']['new_calls'] == 0
    call = final.calls[0]
    assert call.request_sha256 == attempt['request_sha256']
    assert call.length.to_dict() == fixture['input_length']
    for qid, raw in json.loads(attempt['response_raw'])['answers'].items():
        assert call.answers_parsed[qid].probs['true'] == raw['noul']
