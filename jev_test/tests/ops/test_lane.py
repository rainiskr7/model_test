"""무엇: lane 순서·재시도·잠금·정지 검증. 입력: 가짜 실행 환경. 출력: 전송·명령·종료 코드 단언."""

import os
import subprocess
from threading import Thread
import time


def test_ordinary_and_fc_order(sandbox):
    result = sandbox.run(SETS="fc_call_decision")
    assert result.returncode == 0, result.stdout + result.stderr
    commands = sandbox.commands()
    assert [c[0] for c in commands] == ["run", "threshold", "run", "run", "score", "certify"]
    assert [c[c.index("--stage") + 1] for c in commands if c[0] == "run"] == ["dev", "test", "extra"]
    assert len(sandbox.curls.read_text().splitlines()) == 3


def test_kosgd_derived_is_offline_without_health(sandbox):
    result = sandbox.run(SETS="kosgd")
    assert result.returncode == 0, result.stdout + result.stderr
    commands = sandbox.commands()
    assert [c[0] for c in commands] == ["run", "run", "threshold", "threshold", "run", "run",
                                      "score", "certify", "score", "certify"]
    for command in (commands[1], commands[5]):
        assert "--offline" in command and "--base-url" not in command
    assert len(sandbox.curls.read_text().splitlines()) == 2


def test_seal_skips_only_threshold(sandbox):
    seal = sandbox.root / "results/model/r1/A/kmhas/default/test/seal.json"
    seal.parent.mkdir(parents=True)
    seal.write_text("{}")
    assert sandbox.run().returncode == 0
    assert [c[0] for c in sandbox.commands()] == ["run", "run", "score", "certify"]


def test_joint_actions_only_runs_with_health_and_base_url(sandbox):
    result = sandbox.run(args=["joint", "host", "fallback", "1234", "SYNTHETIC_KEY", "r1"], SETS="kosgd")
    assert result.returncode == 0, result.stdout + result.stderr
    runs = [c for c in sandbox.commands() if c[0] == "run"]
    assert [c[c.index("--task") + 1] for c in runs] == [
        f"configs/tasks/kosgd_{variant}.yaml" for variant in ("full", "actions_only", "full", "actions_only")]
    assert [c[c.index("--stage") + 1] for c in runs] == ["dev", "dev", "test", "test"]
    for command in runs:
        assert "--offline" not in command
        assert command[command.index("--base-url") + 1] == "http://fallback:1234"
    assert len(sandbox.curls.read_text().splitlines()) == 4


def test_run_retries_three_times_and_preserves_exit(sandbox):
    result = sandbox.run(FAIL_RUNS="9", FAIL_CODE="17")
    assert result.returncode == 17
    assert [c[0] for c in sandbox.commands()] == ["run"] * 3
    assert len(sandbox.curls.read_text().splitlines()) == 3


def test_run_recovers_then_non_run_failure_is_not_retried(sandbox):
    result = sandbox.run(FAIL_RUNS="1", FAIL_COMMAND="score", FAIL_CODE="19")
    assert result.returncode == 19
    assert [c[0] for c in sandbox.commands()] == ["run", "run", "threshold", "run", "score"]


def test_stop_at_set_boundary(sandbox):
    assert sandbox.run("stop", ["model"]).returncode == 0
    assert sandbox.run().returncode == 4
    assert not sandbox.commands() and not sandbox.curls.exists()


def test_dead_lock_is_reclaimed(sandbox):
    lock = sandbox.root / ".work/ops/lock.model.r1"
    lock.mkdir(parents=True)
    lock.joinpath("owner").write_text("999999999|synthetic start\n")
    assert sandbox.run().returncode == 0
    assert not lock.exists()


def test_live_lane_lock_and_stop_now(sandbox):
    args = ["bash", "ops/lane.sh", "model", "host", "fallback", "1234", "SYNTHETIC_KEY", "r1"]
    process = subprocess.Popen(args, cwd=sandbox.root, env={**sandbox.env, "HOLD": "1"},
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 10
        while not sandbox.calls.exists() and time.monotonic() < deadline:
            time.sleep(.02)
        assert sandbox.calls.exists()
        assert sandbox.run().returncode == 2
        reaper = Thread(target=process.wait, daemon=True)
        reaper.start()
        # Real sleep lets the shell trap reap the owned Python process before verification.
        env = {**sandbox.env, "OPS_TEST_REAL_SLEEP": "1"}
        stopped = subprocess.run(["bash", "ops/stop.sh", "now", "model"], cwd=sandbox.root,
                                 env=env, capture_output=True, text=True, timeout=10)
        assert stopped.returncode == 0, stopped.stdout + stopped.stderr
        assert process.wait(timeout=5) == 143
        reaper.join(timeout=5)
        assert not (sandbox.root / ".work/ops/lock.model.r1").exists()
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)


def test_b1_health_uses_synthetic_ping(sandbox):
    result = sandbox.run(args=["b1", "host", "fallback", "1234", "SYNTHETIC_KEY", "r1"])
    assert result.returncode == 0
    health = sandbox.curls.read_text()
    assert "chat/completions" in health and '"content": "ping"' in health and '"max_tokens": 1' in health
