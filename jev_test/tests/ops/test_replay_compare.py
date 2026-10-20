"""무엇: replay 중단과 compare 덮어쓰기 경계. 입력: 합성 JSON·가짜 CLI. 출력: 순서·오류 단언."""

import json


def test_replay_deferred_stops_that_set(sandbox):
    result = sandbox.run("replay", ["model", "old", "r1", "synthetic reason"], DEFERRED="2")
    assert result.returncode == 3
    assert [c[0] for c in sandbox.commands()] == ["replay", "run"]
    assert "--offline" in sandbox.commands()[1]
    assert not sandbox.curls.exists()


def test_replay_kosgd_order_and_copy_failure(sandbox):
    result = sandbox.run("replay", ["model", "old", "r1", "synthetic reason"], SETS="kosgd")
    assert result.returncode == 0
    commands = sandbox.commands()
    assert [c[0] for c in commands] == ["replay", "run", "run", "threshold", "threshold",
                                      "replay", "run", "run", "score", "certify", "score", "certify"]
    assert all("--offline" in c for c in commands if c[0] == "run")
    assert not sandbox.curls.exists()
    result = sandbox.run("replay", ["model", "old", "r1", "synthetic reason"], FAIL_COMMAND="replay", FAIL_CODE="23")
    assert result.returncode == 23


def test_compare_checks_all_destinations_before_writing(sandbox):
    target = sandbox.root / "results/_compare/r1_kosgd_actions_only/A/kosgd/actions_only/compare.json"
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(dict(schema="compare/1", models=["model", "other"])))
    assert sandbox.run("compare", ["r1", "model", "b1"]).returncode == 2
    assert not sandbox.commands()
    target.write_text(json.dumps(dict(schema="compare/1", models=["b1", "model"])))
    assert sandbox.run("compare", ["r1", "model", "b1"]).returncode == 0
    assert len(sandbox.commands()) == 7


def test_joint_replay_copies_actions_only_before_offline(sandbox):
    result = sandbox.run("replay", ["joint", "old", "r1", "synthetic reason"],
                         SETS="kosgd", SYNTHETIC_KEY="")
    assert result.returncode == 0, result.stdout + result.stderr
    commands = sandbox.commands()
    assert [c[0] for c in commands] == [
        "replay", "run", "replay", "run", "threshold", "threshold",
        "replay", "run", "replay", "run", "score", "certify", "score", "certify"]
    for copy_index, stage in ((2, "dev"), (8, "test")):
        copied, judged = commands[copy_index:copy_index + 2]
        for command in (copied, judged):
            assert command[command.index("--task") + 1] == "configs/tasks/kosgd_actions_only.yaml"
            assert command[command.index("--stage") + 1] == stage
        assert copied[copied.index("--source-run-dir") + 1] == "results/joint/old/A/kosgd/actions_only"
    assert all("--offline" in c and "--base-url" not in c for c in commands if c[0] == "run")
    assert not sandbox.curls.exists()


def test_compare_failure_is_not_hidden(sandbox):
    result = sandbox.run("compare", ["r1", "model", "b1"], FAIL_COMMAND="compare", FAIL_CODE="29")
    assert result.returncode == 29
    assert len(sandbox.commands()) == 1
