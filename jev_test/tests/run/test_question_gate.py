"""질문 봉인 순서·중단·복사·삭제 공격의 통합 검사."""

import pytest

from jeveval.io import run_files
from jeveval.run import cmd_question_risk, gate
from tests.run.registration_support import registered


def test_end_to_end_seal_order_and_frozen_threshold(tmp_path, monkeypatch):
    h = registered(tmp_path, monkeypatch)
    assert h.command("question-threshold") == 0
    writes, original = [], run_files.write_json
    def track(path, value):
        writes.append(path.name)
        return original(path, value)
    monkeypatch.setattr(run_files, "write_json", track)
    h.run("test")
    assert writes.index("question_seal.json") < writes.index("seal.json")
    assert h.command("score") == h.command("certify") == h.command("question-risk") == 0
    risk = run_files.read_json(h.directory / "question_risk.json")
    q = run_files.read_json(h.directory / "question_threshold.json")
    assert risk["registration"]["status"] == "registered"
    for table in ("questions", "diagnostic"):
        for qid, row in risk[table].items():
            assert {t: cell["t_star"] for t, cell in row["by_tau"].items()} == q["by_question"][qid]


@pytest.mark.parametrize("attack", ["delete_question", "delete_main", "tamper", "copy_run", "threshold"])
def test_damaged_seal_hides_numbers_and_rejects_resume(tmp_path, monkeypatch, attack):
    h = registered(tmp_path, monkeypatch)
    assert h.command("question-threshold") == 0
    h.run("test")
    path = h.directory / "test/question_seal.json"
    if attack == "delete_question": path.unlink()
    elif attack == "delete_main": (h.directory / "test/seal.json").unlink()
    elif attack == "threshold": (h.directory / "question_threshold.json").write_text("{}")
    else:
        seal = run_files.read_json(path)
        seal["run_id" if attack == "copy_run" else "question_threshold_sha256"] = "foreign"
        run_files.write_json(path, seal)
    result = cmd_question_risk.run(root=tmp_path, run_dir=h.directory)
    assert result["registration"] == "registration_damaged"
    value = run_files.read_json(h.directory / "question_risk.json")
    assert "questions" not in value and "diagnostic" not in value
    with pytest.raises(ValueError): h.run("test")
    assert h.command("question-threshold") == 1


def test_crash_between_seals_never_recovers_registration(tmp_path, monkeypatch):
    h = registered(tmp_path, monkeypatch)
    assert h.command("question-threshold") == 0
    original = gate.write_seal
    def crash(*a, **kw): raise OSError("synthetic crash")
    monkeypatch.setattr(gate, "write_seal", crash)
    with pytest.raises(OSError): h.run("test")
    assert (h.directory / "test/question_seal.json").exists()
    assert not (h.directory / "test/seal.json").exists()
    monkeypatch.setattr(gate, "write_seal", original)
    with pytest.raises(ValueError): h.run("test")


def test_foreign_threshold_identity_is_rejected_before_test_write(tmp_path, monkeypatch):
    h = registered(tmp_path, monkeypatch)
    h.command("question-threshold")
    path = h.directory / "question_threshold.json"
    value = run_files.read_json(path)
    value["run_id"] = "another_run"
    run_files.write_json(path, value)
    with pytest.raises(ValueError): h.run("test")
    assert not (h.directory / "test").exists()


def test_registered_history_is_exploratory_without_changing_seals(tmp_path, monkeypatch):
    h = registered(tmp_path, monkeypatch)
    h.command("question-threshold")
    h.run("test")
    h.command("score")
    paths = [h.directory / p for p in ("fingerprint.json", "question_threshold.json", "test/question_seal.json", "test/seal.json")]
    before = {p: p.read_bytes() for p in paths}
    result = cmd_question_risk.run(root=tmp_path, run_dir=h.directory, history=True)
    assert result["registration"] == "exploratory"
    assert {p: p.read_bytes() for p in paths} == before
    old = (h.directory / "question_risk.json").read_bytes()
    with pytest.raises(ValueError): cmd_question_risk.run(root=tmp_path, run_dir=h.directory, history=True)
    assert (h.directory / "question_risk.json").read_bytes() == old
