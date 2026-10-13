"""무엇: resume 선검사 짝 시험 · 입력: 계획/기록 변조 · 출력: 전송/쓰기 없는 거부 · 계약 §8-6 B·⑤d R1."""

from dataclasses import replace

import pytest

from jeveval.io import records
from jeveval.run.outcome import call_record, final_record
from jeveval.run.resume_check import check_resume
from tests.run.executor_support import Harness, result
from tests.run.stage_support import snapshot


@pytest.mark.parametrize("failure", ["call", "logical", "hash", "gap", "terminal", "overflow",
                                     "local", "final", "duplicate_final", "duplicate_plan", "budget"])
def test_pure_preflight(env, make_attempt, failure):
    """구조 검사와 계획 연결 검사를 파일 I/O 없이 직접 확인한다."""
    plans, attempts, finals, budget = [env.plan], [make_attempt(env.plan)], [], 5
    if failure in ("call", "logical", "hash", "gap"):
        key = dict(call="call_id", logical="logical_id", hash="request_sha256", gap="attempt")[failure]
        attempts = [replace(attempts[0], **{key: 2 if failure == "gap" else "wrong"})]
    elif failure == "terminal":
        attempts.append(make_attempt(env.plan, attempt=2))
    elif failure == "overflow":
        attempts = [make_attempt(env.plan, attempt=i, terminal=False) for i in range(1, 7)]
    elif failure == "local":
        plans = [replace(env.plan, local_errors=["invalid"])]
    elif failure in ("final", "duplicate_final"):
        call = call_record(env.plan, attempts, env.length, env.cfg)
        final = final_record(env.plan.logical_id, plans, [call])
        finals = [replace(final, logical_id="outside")] if failure == "final" else [final, final]
    elif failure == "duplicate_plan":
        plans *= 2
    else:
        budget = True
    assert check_resume(plans, attempts, finals, budget)


@pytest.mark.parametrize("failure", ["hash", "logical", "unknown", "overflow", "local", "completed"])
def test_all_items_checked_before_first_write_or_send(tmp_path, env, make_attempt, failure):
    """첫 항목이 새 요청이어도 뒤 항목의 잘못된 기록을 발견하면 전체를 무변경 거부한다."""
    h = Harness(tmp_path, env, [result()])
    item = replace(env.item, item_id="later", state_fields=" " if failure == "local" else env.item.state_fields)
    from jeveval.run.plan_calls import plan_calls
    plan, = plan_calls(item, env.task, env.cfg, env.b1)
    attempts = [make_attempt(plan, terminal=False)]
    if failure in ("hash", "completed"):
        attempts = [replace(attempts[0], request_sha256="changed")]
    elif failure == "logical":
        attempts = [replace(attempts[0], logical_id="outside")]
    elif failure == "unknown":
        attempts = [replace(attempts[0], call_id="outside")]
    elif failure == "overflow":
        attempts = [make_attempt(plan, attempt=i, terminal=False) for i in range(1, 7)]
    for row in attempts:
        records.append_record(tmp_path / "dev/attempts.jsonl", row)
    if failure == "completed":
        call = call_record(plan, [make_attempt(plan)], env.length, env.cfg)
        records.append_record(tmp_path / "dev/final.jsonl", final_record(plan.logical_id, [plan], [call]))
    before = snapshot(tmp_path)
    with pytest.raises(ValueError):
        h.run(items=[env.item, item])
    assert snapshot(tmp_path) == before and h.sent == h.measured == []


def test_nonterminal_exhaustion_recovers_without_rewrite(tmp_path, env, make_attempt):
    """terminal 비트가 없는 5회 소진도 다시 보내거나 과거 기록을 고치지 않는다."""
    h = Harness(tmp_path, env)
    path = tmp_path / "dev/attempts.jsonl"
    for number in range(1, 6):
        records.append_record(path, make_attempt(env.plan, attempt=number,
                              terminal=False, http_status=503, response_raw="{}"))
    before = path.read_bytes()
    summary = h.run()
    final = records.read_finals(tmp_path / "dev/final.jsonl")[0][0]
    assert summary.n_recovered == 1 and summary.n_sent == 0
    assert final.reason == "http_503" and path.read_bytes() == before


def test_foreign_final_refused_before_missing_attempt_file_creation(tmp_path, env, make_attempt):
    """items 밖 final은 새 attempts 파일조차 만들기 전에 거부한다."""
    h = Harness(tmp_path, env)
    call = call_record(env.plan, [make_attempt(env.plan)], env.length, env.cfg)
    final = final_record(env.plan.logical_id, [env.plan], [call])
    records.append_record(tmp_path / "dev/final.jsonl", replace(final, logical_id="outside"))
    before = snapshot(tmp_path)
    with pytest.raises(ValueError, match="outside"):
        h.run()
    assert snapshot(tmp_path) == before and not h.sent
