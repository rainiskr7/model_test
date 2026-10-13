"""무엇: 논리 요청 비용 · 입력: final·attempt·kind·파생 출처 · 출력: Cost/단계별 dict · 계약 §7-6."""

from collections import defaultdict
from datetime import datetime
import json
import math

from jeveval.types import AttemptRecord, Cost, FinalRecord


def _percentile(values, p):
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * p
    lo, hi = math.floor(position), math.ceil(position)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (position - lo)


def _usage(attempt, key):
    if attempt is None or not isinstance(attempt.response_raw, str):
        return None
    try:
        body = json.loads(attempt.response_raw)
    except ValueError:
        return None
    usage = body.get("usage") if isinstance(body, dict) else None
    value = usage.get(key) if isinstance(usage, dict) else None
    return value if type(value) is int else None


def _tokens(calls, history, kind):
    total = present = missing = missing_200 = 0
    key = "prompt_tokens" if kind == "b1" else "input_tokens"
    for call_id in calls:
        terminal = max((a for a in history[call_id] if a.terminal),
                       key=lambda a: a.attempt, default=None)
        value = _usage(terminal, key)
        if value is None:
            missing += 1
            missing_200 += int(terminal is not None and terminal.http_status == 200)
        else:
            total += value
            present += 1
    assert present + missing == len(calls)
    return dict(sum=total, n_calls_missing_usage=missing, n_missing_on_200=missing_200)


def _latency(finals, logical_history):
    values, excluded = [], 0
    for final in finals:
        if final.status != "ok":
            continue
        rows = logical_history[final.logical_id]
        if len({a.session_id for a in rows}) > 1:
            excluded += 1
            continue
        terminals = [a for a in rows if a.terminal]
        if not rows or not terminals:
            raise ValueError("ok final requires terminal attempts for latency")
        start = min(datetime.fromisoformat(a.started_at) for a in rows)
        end = max(datetime.fromisoformat(a.ended_at) for a in terminals)
        values.append((end - start).total_seconds() * 1000)
    return dict(population="logical_ok", n=len(values), p50=_percentile(values, .5),
                p95=_percentile(values, .95), n_excluded_resumed=excluded)


def cost(*, finals: list[FinalRecord], attempts: list[AttemptRecord],
         derived_from: str | None, kind: str) -> Cost:
    """직접 실행은 완료 final의 호출을 분모로 삼고 파생 단계는 관측값과 무관하게 0이다."""
    if kind not in ("b1", "systemone"):
        raise ValueError("kind must be b1 or systemone")
    if derived_from is not None:
        return Cost(0, 0, 0, 0, dict(num=0, den=0), _latency([], {}),
                    dict(sum=0, n_calls_missing_usage=0, n_missing_on_200=0), derived_from)
    if any(f.derived_from is not None for f in finals):
        raise ValueError("derived finals require stage derived_from")
    calls = {c.call_id: f.logical_id for f in finals for c in f.calls}
    if (len({f.logical_id for f in finals}) != len(finals)
            or len(calls) != sum(len(f.calls) for f in finals)):
        raise ValueError("duplicate final or call ID")
    history, logical_history = defaultdict(list), defaultdict(list)
    for attempt in attempts:
        if attempt.call_id not in calls or calls[attempt.call_id] != attempt.logical_id:
            raise ValueError("attempt has no matching final call")
        history[attempt.call_id].append(attempt)
        logical_history[attempt.logical_id].append(attempt)
    retries = len(attempts) - len(history)
    return Cost(len(finals), len(calls), len(attempts), retries,
                dict(num=sum(f.status == "error" for f in finals), den=len(finals)),
                _latency(finals, logical_history), _tokens(calls, history, kind), None)


def cost_by_stage(stage_inputs: dict, kind: str) -> dict:
    """단계 출처는 빈 파생 단계도 표현하도록 derived.json에서 호출자가 넘긴다."""
    if stage_inputs.keys() - {"dev", "test", "extra"}:
        raise ValueError("unknown cost stage")
    return {"by_stage": {stage: cost(finals=finals, attempts=attempts,
                                     derived_from=source, kind=kind)
                         for stage, (finals, attempts, source) in stage_inputs.items()}}
