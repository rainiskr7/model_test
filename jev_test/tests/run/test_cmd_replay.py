"""무엇: replay 명령 짝 시험 · 입력: 합성 출처/대상 · 출력: 검사·쓰기 순서·멱등 · 계약 §5-5c."""

from dataclasses import replace

import pytest

from jeveval.io import records, run_files
from jeveval.run import cmd_replay
from jeveval.run.layout import run_dir
from tests.run.cli_support import output_files


def setup(h):
    h.run("dev")
    args = dict(h.args, run_id="r2", stage="dev", source_run_dir=str(h.directory))
    target = run_dir(h.root / "results", "synthetic", "r2", h.set, h.variant)
    return args, target


@pytest.mark.parametrize("failure", ["attempts", "final", "fingerprint", "pending", "newline", "empty", "missing",
    "same_path", "same_id", "reason_long", "reason_line", "hash", "outside", "extra", "target_fingerprint"])
def test_preflight_rejects_without_changes(h, failure):
    args, target = setup(h)
    src = h.directory / "dev/attempts.jsonl"
    if failure in ("attempts", "final"):
        (target / "dev").mkdir(parents=True)
        (target / "dev" / (failure + ".jsonl")).write_bytes(b"")
    elif failure == "fingerprint":
        fp = run_files.read_json(h.directory / "fingerprint.json")
        fp["model"] = "different"
        run_files.write_json(h.directory / "fingerprint.json", fp)
    elif failure in ("pending", "newline", "empty"):
        src.write_bytes(src.read_bytes() + b"{" if failure == "pending" else
                        src.read_bytes().rstrip(b"\n") if failure == "newline" else b"")
    elif failure == "missing":
        src.unlink()
    elif failure == "same_path":
        args["run_id"] = "r1"
    elif failure == "same_id":
        fp = run_files.read_json(h.directory / "fingerprint.json")
        fp["run_id"] = fp["inputs"]["run_id"] = "r2"
        run_files.write_json(h.directory / "fingerprint.json", fp)
    elif failure.startswith("reason"):
        args["reason"] = "a" * 201 if failure == "reason_long" else "a\nb"
    elif failure == "hash":
        row = records.read_attempts(src)[0][0]
        src.write_bytes(records.record_line(replace(row, request_sha256="0" * 64)))
    elif failure == "outside":
        args["source_run_dir"] = "../outside"
    elif failure == "extra":
        args["stage"] = "extra"
    else:
        target.mkdir(parents=True)
        run_files.write_json(target / "fingerprint.json", {})
    before = output_files(h.root)
    with pytest.raises((ValueError, OSError)):
        cmd_replay.run(**args)
    assert output_files(h.root) == before


def test_copy_order_metadata_and_idempotent_repair(h, monkeypatch):
    args, target = setup(h)
    before = output_files(h.directory)
    events, mkdir, write, copy = [], run_files.make_directory, run_files.write_json, run_files.copy_bytes
    def make(path):
        events.append("mkdir")
        mkdir(path)
    def mark(path, value):
        events.append("marker")
        write(path, value)
    def duplicate(src, dst):
        assert (dst.parent / "replay.json").exists()
        events.append("copy")
        copy(src, dst)
    monkeypatch.setattr(run_files, "make_directory", make)
    monkeypatch.setattr(run_files, "write_json", mark)
    monkeypatch.setattr(run_files, "copy_bytes", duplicate)
    assert cmd_replay.run(**args)["ok"]
    assert events == ["mkdir", "marker", "copy"]
    saved = output_files(target)
    metadata = run_files.read_json(target / "dev/replay.json")
    assert set(metadata) == {"schema", "source_run_dir", "source_run_id", "source_code_sha256", "source_env",
                             "source_fingerprint_sha256", "source_attempts_sha256", "source_attempts_nbytes",
                             "copied_at", "reason"}
    assert metadata["schema"] == "replay/1" and metadata["source_run_id"] == "r1"
    assert metadata["source_attempts_nbytes"] == len(before["dev/attempts.jsonl"])
    assert metadata["source_attempts_sha256"] == run_files.file_sha256(h.directory / "dev/attempts.jsonl")
    assert set(saved) == {"dev/replay.json", "dev/attempts.jsonl"}
    assert saved["dev/attempts.jsonl"] == before["dev/attempts.jsonl"]
    for value in h.markers.values():
        assert value.encode() not in saved["dev/replay.json"]
    assert b"private-test-key" not in saved["dev/replay.json"]
    assert cmd_replay.run(**args)["ok"] and output_files(target) == saved
    (target / "dev/attempts.jsonl").unlink()
    assert cmd_replay.run(**args)["ok"] and output_files(target) == saved
    assert output_files(h.directory) == before


@pytest.mark.parametrize("failure", ["attempts", "source", "reason", "final"])
def test_existing_replay_conflicts_are_unchanged(h, failure):
    args, target = setup(h)
    cmd_replay.run(**args)
    if failure == "attempts":
        (target / "dev/attempts.jsonl").write_bytes(b"different")
    elif failure == "source":
        marker = target / "dev/replay.json"
        data = run_files.read_json(marker)
        data["source_run_dir"] = "different"
        run_files.write_json(marker, data)
    elif failure == "reason":
        args["reason"] = "changed"
    else:
        (target / "dev/final.jsonl").write_bytes(b"")
    before = output_files(h.root)
    with pytest.raises(ValueError):
        cmd_replay.run(**args)
    assert output_files(h.root) == before


def test_copy_failure_recovers_from_written_marker(h, monkeypatch):
    args, target = setup(h)
    copy = run_files.copy_bytes
    def fail(*args):
        raise OSError("interrupted")
    monkeypatch.setattr(run_files, "copy_bytes", fail)
    with pytest.raises(OSError):
        cmd_replay.run(**args)
    marker = (target / "dev/replay.json").read_bytes()
    assert not (target / "dev/attempts.jsonl").exists()
    monkeypatch.setattr(run_files, "copy_bytes", copy)
    cmd_replay.run(**args)
    assert (target / "dev/replay.json").read_bytes() == marker


def test_source_old_code_and_environment_are_recorded(h):
    args, target = setup(h)
    path = h.directory / "fingerprint.json"
    source = run_files.read_json(path)
    source.update(code_sha256="a" * 64, env={"python": "old"}, started_at="old")
    run_files.write_json(path, source)
    cmd_replay.run(**args)
    marker = run_files.read_json(target / "dev/replay.json")
    assert marker["source_code_sha256"] == "a" * 64 and marker["source_env"] == {"python": "old"}
    assert marker["source_fingerprint_sha256"] == run_files.file_sha256(path)


def test_derived_replay_rejected_without_changes(tmp_path, monkeypatch):
    from tests.run.cli_support import Harness
    h = Harness(tmp_path, "kosgd", "full")
    monkeypatch.setenv("JEV_TEST_KEY", "key")
    args, _ = setup(h)
    args["task"] = "configs/tasks/kosgd_actions_only.yaml"
    before = output_files(h.root)
    with pytest.raises(ValueError, match="derived variants"):
        cmd_replay.run(**args)
    assert output_files(h.root) == before
