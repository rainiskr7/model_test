"""무엇: overlay 동결 증거 · 입력: 합성 셋·변조 · 출력: 지문·역사 재구성 거부 · 계약 판 5 보정 1 §1-2."""

from types import SimpleNamespace

import pytest

from jeveval.io.config import read_yaml
from jeveval.io.history_inputs import checked_task
from jeveval.run import context, replay_check
from tests.run.cli_support import Harness
from tests.run.file_support import put_yaml


def test_overlay_dependencies_are_hashed_and_checked_for_history(tmp_path):
    h = Harness(tmp_path, "kosgd2", "full")
    path = tmp_path / "configs/sets/kosgd2.yaml"
    value = read_yaml(path)
    value["split_rules"]["pool"] = dict(kind="fixed_selection", path="selection.json",
        exclude=[dict(path="fixture.json", field="cases", by="state_ref")])
    put_yaml(path, value)
    (tmp_path / "selection.json").write_text('{"selected_turns": []}')
    (tmp_path / "fixture.json").write_text('{"schema": "t0_fixture/1", "cases": []}')
    ctx = context.configuration(tmp_path, h.args["model"], h.args["task"])
    before = context.fingerprint(ctx, "r1", "fixed")
    expected = {"configs/sets/kosgd2.yaml", "configs/tasks/kosgd2_full.yaml",
                "configs/tasks/kosgd2_actions_only.yaml", "selection.json", "fixture.json"}
    assert expected <= before["files"].keys()
    saved = SimpleNamespace(artifacts={"fingerprint.json": before})
    assert checked_task(tmp_path, saved) == h.args["task"]
    (tmp_path / "configs/sets/unrelated.yaml").write_text("invalid: [")
    assert context.fingerprint(ctx, "r1", "fixed") == before
    for name in sorted(expected):
        target = tmp_path / name
        original = target.read_bytes()
        target.write_bytes(original + b"\n")
        after = context.fingerprint(ctx, "r1", "fixed")
        assert replay_check.compatible(before, after) == ["files differs"]
        with pytest.raises(ValueError, match="historical item inputs differ"):
            checked_task(tmp_path, saved)
        target.write_bytes(original)
    omitted = {**before, "files": {k: v for k, v in before["files"].items() if k != "fixture.json"}}
    with pytest.raises(ValueError, match="evidence unavailable"):
        checked_task(tmp_path, SimpleNamespace(artifacts={"fingerprint.json": omitted}))
