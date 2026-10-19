"""무엇: all 명령 사전 검사 · 입력: 정상 셋 뒤 실패 셋 · 출력: 파일/표준출력 무변경 · 계약 판 5 보정 1 §9."""

import json

import pytest

from jeveval.run import make_splits, item_summary
from tests.run.cli_support import put_yaml
from tests.run.test_make_splits import _synthetic_rules
from tests.run.test_item_summary import _prepare


def test_all_split_plans_validate_before_any_write(tmp_path, capsys):
    rules = _synthetic_rules(tmp_path)
    rules["sets"]["kote_escalation"]["expect_groups"] = 999
    put_yaml(tmp_path / "rules.yaml", rules)
    out = tmp_path / "out"
    out.mkdir()
    sentinel = out / "fc_call_decision.json"
    sentinel.write_bytes(b"preserve existing bytes")
    with pytest.raises(SystemExit):
        make_splits.main(["--root", str(tmp_path), "--rules", "rules.yaml", "--set", "all", "--out", str(out)])
    assert capsys.readouterr().out == ""
    assert {p.name: p.read_bytes() for p in out.iterdir()} == {sentinel.name: b"preserve existing bytes"}


def test_bad_overlay_rejects_all_but_not_single_split(tmp_path, capsys):
    _synthetic_rules(tmp_path)
    put_yaml(tmp_path / "configs/sets/zzz.yaml", {"schema": "bad"})
    out = tmp_path / "out"
    args = ["--root", str(tmp_path), "--rules", "rules.yaml", "--out", str(out), "--set"]
    with pytest.raises(SystemExit):
        make_splits.main(args + ["all"])
    assert not out.exists() and capsys.readouterr().out == ""
    assert make_splits.main(args + ["kmhas"]) == 0
    assert [p.name for p in out.iterdir()] == ["kmhas.json"]


def test_summary_all_does_not_emit_partial_output(tmp_path, capsys):
    _prepare(tmp_path)
    (tmp_path / "tasks/zzz.yaml").write_text("bad: task")
    args = ["--root", str(tmp_path), "--rules", "rules.yaml", "--tasks", "tasks", "--splits", "splits", "--task"]
    with pytest.raises(SystemExit):
        item_summary.main(args + ["all"])
    assert capsys.readouterr().out == ""
    assert item_summary.main(args + ["fc"]) == 0
    assert json.loads(capsys.readouterr().out)["task"] == "fc"
