"""무엇: offline 실행 경계 · 입력: 부분 기록·로컬 오류 · 출력: 무전송/미룸/재개 · 계약 §5-5c."""

from dataclasses import replace

from jeveval.io import records
from jeveval.run.plan_calls import plan_calls
from tests.run.executor_support import Harness, result


def test_offline_mixed_items_then_resume(tmp_path, env, make_attempt):
    h = Harness(tmp_path, env, [result(), result()])
    items = [replace(env.item, item_id=name) for name in ("complete", "retry", "missing", "local")]
    items[-1] = replace(items[-1], state_fields=" ")
    plans = [plan_calls(i, env.task, env.cfg, env.b1)[0] for i in items]
    path = tmp_path / "dev/attempts.jsonl"
    records.append_record(path, make_attempt(plans[0]))
    records.append_record(path, make_attempt(plans[1], terminal=False, http_status=503))
    before = path.read_bytes()
    summary = h.run(items=items, offline=True)
    assert (summary.n_sent, summary.n_recovered, summary.n_deferred) == (0, 1, 2)
    assert h.sent == h.waits == [] and path.read_bytes() == before
    assert {f.logical_id for f in records.read_finals(tmp_path / "dev/final.jsonl")[0]} == {
        plans[0].logical_id, plans[-1].logical_id}
    summary = h.run(items=items)
    assert summary.n_sent == 2 and summary.n_skipped_final == 2 and summary.n_deferred == 0
    attempts, _ = records.read_attempts(path)
    assert [a.attempt for a in attempts if a.call_id == plans[1].call_id] == [1, 2]
    assert len(records.read_finals(tmp_path / "dev/final.jsonl")[0]) == 4


def test_offline_defers_whole_partial_b1_item(tmp_path, env, make_attempt):
    h = Harness(tmp_path, env)
    item = replace(env.item, questions=[replace(env.q, id="a"), replace(env.q, id="b")])
    cfg = replace(env.bcfg, base_url="http://replay.invalid")
    plans = plan_calls(item, env.task, cfg, env.b1)
    path = tmp_path / "dev/attempts.jsonl"
    records.append_record(path, make_attempt(plans[0]))
    before = path.read_bytes()
    summary = h.run(items=[item], cfg=cfg, offline=True)
    assert summary.n_deferred == 1 and summary.n_calls == summary.n_sent == 0
    assert not h.measured and not h.sent and path.read_bytes() == before
    assert records.read_finals(tmp_path / "dev/final.jsonl")[0] == []


def test_offline_recovers_exhausted_nonterminal_budget(tmp_path, env, make_attempt):
    h = Harness(tmp_path, env)
    for number in range(1, env.policy.max_attempts + 1):
        records.append_record(tmp_path / "dev/attempts.jsonl", make_attempt(
            env.plan, attempt=number, terminal=False, http_status=503))
    summary = h.run(offline=True)
    assert summary.n_recovered == 1 and summary.n_deferred == summary.n_sent == 0
    assert not h.sent
