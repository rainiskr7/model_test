"""무엇: 비용 fixture 검산 · 입력: 합성 시도·상태 · 출력: 집계 대조 · 계약 §5-3·§7-6."""

from datetime import datetime
import json
import math

import pytest

from jeveval.types import AttemptRecord, Cost
from test_fixtures_wellformed import ROOT, read


def percentile(values, p):
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered)-1)*p
    lo, hi = math.floor(position), math.ceil(position)
    return ordered[lo] + (ordered[hi]-ordered[lo])*(position-lo)


def integer_usage(response_raw, token_key):
    if not isinstance(response_raw, str):
        return None
    try:
        body = json.loads(response_raw)
    except ValueError:
        return None
    usage = body.get('usage') if isinstance(body, dict) else None
    value = usage.get(token_key) if isinstance(usage, dict) else None
    return value if type(value) is int else None


def check_input_tokens(attempts, token_key, expected):
    calls = {a.call_id for a in attempts}
    terminal = {call:max((a for a in attempts if a.call_id == call and a.terminal),
                        key=lambda a:a.attempt, default=None) for call in calls}
    usage = {call:integer_usage(a.response_raw, token_key) if a else None
             for call,a in terminal.items()}
    assert expected.input_tokens == {
        'sum':sum(v for v in usage.values() if v is not None),
        'n_calls_missing_usage':sum(v is None for v in usage.values()),
        'n_missing_on_200':sum(v is None and terminal[call] is not None
                              and terminal[call].http_status == 200 for call,v in usage.items())}
    assert sum(v is not None for v in usage.values()) + expected.input_tokens['n_calls_missing_usage'] == expected.n_calls


def test_cost_attempts_sessions_and_usage():
    for case in read(ROOT / 'scoring/cost.json')['cases']:
        expected = Cost.from_dict(case['expected'])
        if case['derived_from']:
            assert expected.derived_from == case['derived_from']
            assert expected.n_calls == expected.n_attempts == expected.n_retries == expected.n_logical == 0
            assert expected.failure == {'num':0,'den':0}
            assert expected.input_tokens == {'sum':0,'n_calls_missing_usage':0,'n_missing_on_200':0}
            assert 0 + expected.input_tokens['n_calls_missing_usage'] == expected.n_calls
            assert expected.latency_ms == dict(population='logical_ok', n=0, p50=None, p95=None, n_excluded_resumed=0)
            continue
        attempts = [AttemptRecord.from_dict(a) for a in case['attempts']]
        statuses = case['logical_statuses']
        calls = {a.call_id for a in attempts}
        assert expected.n_calls == len(calls)
        assert expected.n_attempts == len(attempts)
        assert expected.n_retries == len(attempts)-len(calls)
        assert expected.n_logical == len(statuses)
        assert expected.failure == {'num':sum(s=='error' for s in statuses.values()),'den':len(statuses)}
        values, excluded = [], 0
        for lid, status in statuses.items():
            if status != 'ok':
                continue
            rows = [a for a in attempts if a.logical_id == lid]
            if len({a.session_id for a in rows}) > 1:
                excluded += 1
            else:
                start = min(datetime.fromisoformat(a.started_at) for a in rows)
                end = max(datetime.fromisoformat(a.ended_at) for a in rows if a.terminal)
                values.append((end-start).total_seconds()*1000)
        assert expected.latency_ms == pytest.approx(dict(population='logical_ok', n=len(values),
            p50=percentile(values,.5), p95=percentile(values,.95), n_excluded_resumed=excluded))
        token_key = 'prompt_tokens' if case['provider']=='b1' else 'input_tokens'
        check_input_tokens(attempts, token_key, expected)
        if case['name'] == 'b1_kosgd':
            assert expected.n_calls == 12*expected.n_logical
