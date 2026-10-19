"""순수 등록 검증과 개발 재계산 불일치 검사."""

from jeveval.io import question_registration as io
from jeveval.run.question_registration import check
from tests.run.registration_support import registered


def test_registered_chain_and_recomputed_mismatch(tmp_path, monkeypatch):
    h = registered(tmp_path, monkeypatch)
    h.command("question-threshold")
    h.run("test")
    e = io.read(tmp_path, h.directory)
    assert check(e) == "registered"
    assert check(e, {}) == "registration_damaged"
    e["artifacts"]["question_threshold.json"]["taus"].append("0.2")
    assert check(e) == "registration_damaged"


def test_declared_without_threshold_is_not_registered(tmp_path, monkeypatch):
    h = registered(tmp_path, monkeypatch)
    assert check(io.read(tmp_path, h.directory)) == "registration_damaged"
