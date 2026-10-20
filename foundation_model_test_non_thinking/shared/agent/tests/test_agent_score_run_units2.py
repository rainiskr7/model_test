"""9-1b CLI contracts captured before extraction, using only temporary files."""

import json
from pathlib import Path

import pytest

from shared.agent.scoring import score_run as scorer


SUMMARY_BYTES = '{\n  "levels_missing": [],\n  "value": "합성"\n}'.encode("utf-8")


@pytest.fixture
def inputs(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    root = Path("session")
    root.mkdir()
    (root / "summary.json").write_bytes(b"previous summary\n")
    (root / "summary.invalid.json").write_bytes(b"previous sidecar\n")
    summary = {"levels_missing": [], "value": "합성"}
    calls = []
    monkeypatch.setattr(scorer, "_result_dir_from_args", lambda args: root)
    monkeypatch.setattr(scorer, "load_metrics_module", lambda: calls.append("bootstrap"))

    def build(path):
        calls.append(("build", path))
        return summary

    def table(value, skipped):
        assert value is summary and skipped == 0
        calls.append("table")
        print("synthetic table")

    monkeypatch.setattr(scorer, "build_summary", build)
    monkeypatch.setattr(scorer, "print_table", table)
    monkeypatch.setattr(scorer, "validate_summary", lambda value, path: ([], ["synthetic warning"]))
    return root, summary, calls


@pytest.mark.parametrize("rejected,dry_run,rc,tail", [
    (False, False, 0, "[agent-scoring] wrote session/summary.json\n"),
    (True, False, 1, "[agent-scoring] FAIL rejected\n[agent-scoring] wrote session/summary.invalid.json\n"),
    (False, True, 0, ""),
    (True, True, 1, "[agent-scoring] FAIL rejected\n"),
])
def test_save_policy_bytes_rc_and_patch_reach(inputs, monkeypatch, capsys, rejected, dry_run, rc, tail):
    root, summary, calls = inputs

    def validate(value, path):
        assert value is summary and path == root
        calls.append("validate")
        return (["rejected"] if rejected else []), ["synthetic warning"]

    monkeypatch.setattr(scorer, "validate_summary", validate)
    assert scorer.main(["--dry-run"] if dry_run else []) == rc
    assert calls == ["bootstrap", ("build", root), "table", "validate"]
    assert capsys.readouterr() == ("synthetic table\n[agent-scoring] WARN synthetic warning\n" + tail, "")
    assert (root / "summary.json").read_bytes() == (
        SUMMARY_BYTES if not rejected and not dry_run else b"previous summary\n"
    )
    if not rejected and not dry_run:
        assert not (root / "summary.invalid.json").exists()
    else:
        assert (root / "summary.invalid.json").read_bytes() == (
            SUMMARY_BYTES if rejected and not dry_run else b"previous sidecar\n"
        )


@pytest.mark.parametrize("drift,rejected,rc,tail", [
    (False, False, 0, "[agent-scoring] CHECK summary.json matches computed summary\n"),
    (False, True, 3, "[agent-scoring] FAIL rejected\n"
     "[agent-scoring] CHECK summary.json matches computed summary but validation failed\n"),
    (True, True, 1, "[agent-scoring] FAIL rejected\n"
     '[agent-scoring] DRIFT .value stored="old" computed="합성"\n'),
])
def test_check_precedence_and_no_writes(inputs, monkeypatch, capsys, drift, rejected, rc, tail):
    root, summary, _ = inputs
    stored = dict(summary, value="old") if drift else summary
    (root / "summary.json").write_text(json.dumps(stored), encoding="utf-8")
    before = (root / "summary.json").read_bytes()
    monkeypatch.setattr(scorer, "validate_summary", lambda *args: (["rejected"] if rejected else [], []))
    assert scorer.main(["--check"]) == rc
    assert capsys.readouterr() == ("synthetic table\n" + tail, "")
    assert (root / "summary.json").read_bytes() == before
    assert (root / "summary.invalid.json").read_bytes() == b"previous sidecar\n"


def test_sidecar_is_deleted_before_patched_writer_failure(inputs, monkeypatch, capsys):
    root, summary, _ = inputs
    calls = []

    def fail_write(path, value):
        calls.append((path, value is summary, (root / "summary.invalid.json").exists()))
        raise OSError("synthetic write failure")

    monkeypatch.setattr(scorer, "_write_json_atomic", fail_write)
    assert scorer.main([]) == 2
    assert calls == [(root / "summary.json", True, False)]
    assert (root / "summary.json").read_bytes() == b"previous summary\n"
    assert capsys.readouterr() == (
        "synthetic table\n[agent-scoring] WARN synthetic warning\n",
        "[agent-scoring] error: OSError: synthetic write failure\n",
    )


def test_check_missing_summary_fails_before_bootstrap(inputs, capsys):
    root, _, calls = inputs
    (root / "summary.json").unlink()
    assert scorer.main(["--check"]) == 2
    assert calls == []
    assert capsys.readouterr() == (
        "", "[agent-scoring] error: RuntimeError: summary.json not found: session/summary.json\n",
    )
    assert (root / "summary.invalid.json").read_bytes() == b"previous sidecar\n"


def test_argument_parser_error_remains_value_error_and_main_returns_two(capsys):
    with pytest.raises(ValueError, match="^unrecognized arguments: --unknown-option$"):
        scorer.parse_args(["--unknown-option"])
    assert scorer.main(["--unknown-option"]) == 2
    assert capsys.readouterr() == (
        "", "[agent-scoring] error: ValueError: unrecognized arguments: --unknown-option\n",
    )
