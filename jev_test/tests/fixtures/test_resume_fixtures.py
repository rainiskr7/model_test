"""무엇: resume 입력·기대 기록 검사 · 입력: 합성 JSONL · 출력: 검증 · 계약 §5-3·§5-5."""

import json

from jeveval.types import AttemptRecord, FinalRecord
from test_fixtures_wellformed import ROOT, read


def test_broken_lines_preserve_only_complete_records():
    for name in ('broken_last_line','broken_middle_line'):
        f = read(ROOT / f'resume/{name}.json')
        lines = f['attempts_jsonl'].splitlines()
        good, broken = [], []
        for index, line in enumerate(lines):
            try:
                good.append(AttemptRecord.from_dict(json.loads(line)))
            except json.JSONDecodeError:
                broken.append(index)
        assert f['expected']['refuse'] == any(i != len(lines)-1 for i in broken)
        if name == 'broken_last_line':
            assert [r.to_dict() for r in good] == f['expected']['kept_attempts']
            assert f['expected']['discard_last_line'] and f['expected']['warning_required']


def test_completed_and_duplicate_ids():
    for name in ('completed_id','duplicate_id'):
        f = read(ROOT / f'resume/{name}.json')
        records = [FinalRecord.from_dict(json.loads(line)) for line in f['final_jsonl'].splitlines()]
        ids = [r.logical_id for r in records]
        if name == 'duplicate_id':
            assert (len(ids) != len(set(ids))) == f['expected']['refuse']
        else:
            assert ids == f['expected']['skip_logical_ids']
            assert f['expected']['new_calls'] == 0


def test_retry_budget_across_attempt_records():
    f = read(ROOT / 'resume/retry_budget.json')
    for case in f['cases']:
        attempts = [AttemptRecord.from_dict(a) for a in case['attempts']]
        pending = {a.call_id for a in attempts} - {a.call_id for a in attempts if a.terminal}
        expected = case['expected']
        if not pending:
            assert expected['remaining_attempts'] == expected['new_calls'] == 0
        else:
            for call in pending:
                used = max(a.attempt for a in attempts if a.call_id == call)
                assert expected['remaining_attempts'] == f['max_attempts']-used
                assert expected['next_attempt'] == used+1
