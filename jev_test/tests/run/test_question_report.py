"""등록 보고는 선언 문자열 대신 증거 사슬과 재계산을 확인한다."""

from jeveval.io import history, run_files
from jeveval.run.question_report import status
from tests.run.registration_support import registered


def test_report_validates_registration_and_statistics(tmp_path, monkeypatch):
    h = registered(tmp_path, monkeypatch)
    h.command("question-threshold")
    h.run("test")
    h.command("score")
    h.command("question-risk")
    saved = history.read(tmp_path, h.directory)
    value = saved.artifacts["question_risk.json"]
    assert status(tmp_path, saved, value) == "registered"
    value["questions"]["ongoing_bundle"]["by_tau"]["0.02"]["n_accepted"] = 123
    assert status(tmp_path, saved, value) == "registration_damaged"
