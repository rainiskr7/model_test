"""무엇: 분석 CLI 분기 · 입력: 명령 인자 · 출력: 정확한 핸들러 인자 · 계약 §8-1."""

from jeveval.run import cli


def test_report_cli_explicit_compare_and_unrun_dispatch(monkeypatch, capsys):
    received = {}
    def run(**args):
        received.update(args)
        return {"ok": True}
    monkeypatch.setattr(cli.cmd_report, "run", run)
    assert cli.main(["report", "--run-id", "r", "--models", "m", "--compare-id", "c", "--note-unrun", "clef"]) == 0
    assert received["compare_id"] == ["c"] and received["note_unrun"] == ["clef"]
    assert '"ok":true' in capsys.readouterr().out


def test_question_risk_history_flag_dispatch(monkeypatch):
    received = {}
    def run(**args):
        received.update(args)
        return {"ok": True}
    monkeypatch.setattr(cli.cmd_question_risk, "run", run)
    assert cli.main(["question-risk", "--run-dir", "run", "--history"]) == 0
    assert received["history"] is True
