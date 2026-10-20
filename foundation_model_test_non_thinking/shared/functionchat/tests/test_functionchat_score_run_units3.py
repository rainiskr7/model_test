"""9-1b CLI output, publication and IO ordering on synthetic raw artifacts."""

from pathlib import Path

import pytest

from shared.functionchat.scoring import score_run as scorer


SCORES = (
    "[functionchat-scoring] singlecall: 1/2 accuracy=0.500000\n"
    "[functionchat-scoring] call_decision: 0/0 accuracy=n/a (measured=0)\n"
    "[functionchat-scoring] overall: 1/2 accuracy=0.500000; not_measured=3\n"
)
REJECTED_BYTES = b'''{
  "scoring_version": "synthetic",
  "by_dataset": {
    "singlecall": {
      "passed": 1,
      "measured": 2,
      "accuracy": 0.5
    },
    "call_decision": {
      "passed": 0,
      "measured": 0,
      "accuracy": null
    }
  },
  "overall": {
    "passed": 1,
    "measured": 2,
    "accuracy": 0.5
  },
  "not_measured": {
    "total_items": 3
  },
  "publish_status": {
    "publishable": false,
    "failures": [
      "rejected"
    ],
    "warnings": [
      "synthetic warning"
    ],
    "gate_scoring_version": "synthetic"
  }
}
'''


@pytest.fixture
def inputs(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    root = Path("session")
    root.mkdir()
    for name in ("singlecall", "call_decision", "dialog", "coverage"):
        (root / f"{name}.json").write_text("{}", encoding="utf-8")
    (root / "summary.json").write_bytes(b"previous\n")
    summary = {
        "scoring_version": "synthetic",
        "by_dataset": {"singlecall": {"passed": 1, "measured": 2, "accuracy": 0.5},
                       "call_decision": {"passed": 0, "measured": 0, "accuracy": None}},
        "overall": {"passed": 1, "measured": 2, "accuracy": 0.5},
        "not_measured": {"total_items": 3},
    }
    calls = []
    monkeypatch.setattr(scorer, "_results_dir", lambda args: root)

    def load(path):
        calls.append(path.name)
        return {"source": path.stem}

    def build(raw, coverage, track):
        calls.append(("build", list(raw), coverage, track))
        return summary

    def validate(value):
        assert value is summary and "publish_status" not in value
        calls.append("validate")
        return ["rejected"], ["synthetic warning"]

    monkeypatch.setattr(scorer, "_load", load)
    monkeypatch.setattr(scorer, "build_summary", build)
    monkeypatch.setattr(scorer, "validate_summary", validate)
    return root, summary, calls


@pytest.mark.parametrize("dry_run", [False, True])
def test_rejected_summary_and_dry_run_only_skip_storage(inputs, capsys, dry_run):
    root, summary, calls = inputs
    assert scorer.main(["--dry-run"] if dry_run else []) == 1
    assert calls == [
        "singlecall.json", "call_decision.json", "dialog.json", "coverage.json",
        ("build", ["singlecall", "call_decision", "dialog"], {"source": "coverage"}, "functionchat"),
        "validate",
    ]
    assert summary["publish_status"] == {
        "publishable": False, "failures": ["rejected"], "warnings": ["synthetic warning"],
        "gate_scoring_version": "synthetic",
    }
    assert (root / "summary.json").read_bytes() == (b"previous\n" if dry_run else REJECTED_BYTES)
    assert capsys.readouterr() == (
        SCORES + ("" if dry_run else "[functionchat-scoring] wrote session/summary.json\n"),
        "[functionchat-scoring] WARN: synthetic warning\n[functionchat-scoring] FAIL: rejected\n"
        "[functionchat-scoring] NOT PUBLISHABLE: 1건의 검증 실패\n",
    )


def test_writer_patch_runs_after_status_and_before_rejection_message(inputs, monkeypatch, capsys):
    root, summary, _ = inputs
    calls = []

    def fail_write(path, value):
        calls.append((path, value is summary, value["publish_status"]["publishable"]))
        raise OSError("synthetic write failure")

    monkeypatch.setattr(scorer, "write_json_atomic", fail_write)
    assert scorer.main([]) == 2
    assert calls == [(root / "summary.json", True, False)]
    assert (root / "summary.json").read_bytes() == b"previous\n"
    assert capsys.readouterr() == (
        SCORES, "[functionchat-scoring] WARN: synthetic warning\n[functionchat-scoring] FAIL: rejected\n"
        "[functionchat-scoring] ERROR: OSError: synthetic write failure\n",
    )


def test_required_raw_missing_stops_before_coverage_or_scoring(inputs, capsys):
    root, _, calls = inputs
    (root / "call_decision.json").unlink()
    assert scorer.main([]) == 2
    assert calls == ["singlecall.json"]
    assert (root / "summary.json").read_bytes() == b"previous\n"
    assert capsys.readouterr() == (
        "", "[functionchat-scoring] ERROR: FileNotFoundError: "
        "required raw artifact missing: session/call_decision.json\n",
    )


def test_optional_raw_absence_keeps_read_order_and_success_rc(inputs, monkeypatch, capsys):
    root, _, calls = inputs
    (root / "dialog.json").unlink()
    monkeypatch.setattr(scorer, "validate_summary", lambda value: ([], []))
    assert scorer.main(["--dry-run"]) == 0
    assert calls == ["singlecall.json", "call_decision.json", "coverage.json",
                     ("build", ["singlecall", "call_decision"], {"source": "coverage"}, "functionchat")]
    assert capsys.readouterr() == (SCORES, "")
    assert (root / "summary.json").read_bytes() == b"previous\n"


def test_score_print_failure_keeps_preceding_dataset_output(inputs, capsys):
    root, summary, calls = inputs
    del summary["overall"]["accuracy"]
    assert scorer.main([]) == 2
    assert "validate" not in calls
    assert capsys.readouterr() == (
        "[functionchat-scoring] singlecall: 1/2 accuracy=0.500000\n"
        "[functionchat-scoring] call_decision: 0/0 accuracy=n/a (measured=0)\n",
        "[functionchat-scoring] ERROR: KeyError: 'accuracy'\n",
    )
    assert (root / "summary.json").read_bytes() == b"previous\n"
