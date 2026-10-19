"""질문 threshold의 등록/개발/시험 경계를 검증한다."""

import pytest

from jeveval.io import run_files
from jeveval.run import cmd_question_threshold
from tests.run.registration_support import registered


def test_registered_threshold_binds_identity_manifest_dev(tmp_path, monkeypatch):
    h = registered(tmp_path, monkeypatch)
    assert h.command("question-threshold") == 0
    q = run_files.read_json(h.directory / "question_threshold.json")
    fp = run_files.read_json(h.directory / "fingerprint.json")
    assert q["manifest_sha256"] == fp["files"][q["manifest"]]
    assert q["questions"] == sorted(q["by_question"])
    assert q["run_id"] == "r1" and "ongoing_bundle" in q["questions"]
    with pytest.raises(ValueError):
        cmd_question_threshold.run(root=tmp_path, run_dir=h.directory)


@pytest.mark.parametrize("name", ["seal.json", "question_seal.json", "attempts.jsonl", "final.jsonl", "derived.json", "replay.json"])
def test_empty_test_artifact_is_started(tmp_path, monkeypatch, name):
    h = registered(tmp_path, monkeypatch)
    (h.directory / "test").mkdir()
    (h.directory / "test" / name).touch()
    with pytest.raises(ValueError):
        cmd_question_threshold.run(root=tmp_path, run_dir=h.directory)
    assert not (h.directory / "question_threshold.json").exists()


def test_ordinary_threshold_required(tmp_path, monkeypatch):
    h = registered(tmp_path, monkeypatch)
    (h.directory / "threshold.json").unlink()
    with pytest.raises(OSError):
        cmd_question_threshold.run(root=tmp_path, run_dir=h.directory)
