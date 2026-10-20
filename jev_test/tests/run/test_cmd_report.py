"""무엇: 보고 명령 공개 경계 · 입력: 합성 run·손상 · 출력: 안전한 Markdown · 계약 §7-6."""

import shutil

import pytest

from jeveval.io import run_files
from jeveval.run import cli, cmd_report
from tests.run.file_support import output_files
from tests.run.history_support import finished


def test_two_models_report_canary_and_input_unchanged(tmp_path, monkeypatch, capsys):
    h = finished(tmp_path, monkeypatch)
    capsys.readouterr()
    other = tmp_path / "results/second/r1/A/klue_mrc_answerable/default"
    shutil.copytree(h.directory, other)
    for name in ("fingerprint.json", "threshold.json", "risk.json", "scores.json", "summary.json"):
        data = run_files.read_json(other / name)
        data["model"] = "second"
        run_files.write_json(other / name, data)
    # 두 번째 모델은 seal 해시가 어긋나므로 손상 행이어야 한다.
    before = output_files(tmp_path / "results")
    assert cli.main(["report", "--run-id", "r1", "--models", "synthetic", "second", "--out", "report.md"]) == 0
    text = (tmp_path / "report.md").read_text()
    assert "verified_complete" in text and "damaged" in text and "UNDERPOWERED" in text
    assert output_files(tmp_path / "results") == before
    public = text + str(capsys.readouterr())
    for marker in h.markers.values():
        assert marker not in public
    assert str(tmp_path) not in public


@pytest.mark.parametrize("fault", ["missing", "tail", "identity", "seal"])
def test_incomplete_and_damaged_have_no_risk_numbers(tmp_path, monkeypatch, fault):
    h = finished(tmp_path, monkeypatch)
    if fault in ("missing", "tail"):
        p = h.directory / "test/final.jsonl"
        p.write_text("" if fault == "missing" else p.read_text() + "{")
    else:
        p = h.directory / ("risk.json" if fault == "identity" else "test/seal.json")
        value = run_files.read_json(p)
        value["model" if fault == "identity" else "threshold_sha256"] = "PRIVATE_CANARY"
        run_files.write_json(p, value)
    cmd_report.run(root=tmp_path, run_id="r1", models=["synthetic"], out="report.md")
    text = (tmp_path / "report.md").read_text()
    assert "PRIVATE_CANARY" not in text and "UNDERPOWERED" not in text.split("###", 1)[1]
    assert ("incomplete" if fault in ("missing", "tail") else "damaged") in text


def test_outside_output_rejected_before_write(tmp_path, monkeypatch):
    h = finished(tmp_path, monkeypatch)
    before = output_files(tmp_path)
    with pytest.raises(ValueError):
        cmd_report.run(root=tmp_path, run_id="r1", models=["synthetic"], out="../escape.md")
    assert output_files(tmp_path) == before


def test_kosgd_incomplete_test_still_decomposes_verified_dev(tmp_path, monkeypatch):
    h = finished(tmp_path, monkeypatch, "kosgd", "full")
    (h.directory / "test/final.jsonl").write_text("")
    cmd_report.run(root=tmp_path, run_id="r1", models=["synthetic"], out="report.md")
    text = (tmp_path / "report.md").read_text()
    assert "개발 표본 진단" in text and "정답/칸만/행동만/둘 다" in text


def test_cli_error_never_prints_private_output_path(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert cli.main(["report", "--run-id", "r", "--models", "m", "--out", "../PRIVATE_RAW.md"]) == 1
    assert "PRIVATE_RAW" not in str(capsys.readouterr())
    assert not list(tmp_path.iterdir())


def test_verified_models_exact_compare_and_exploratory_table(tmp_path, monkeypatch):
    from jeveval.run import cmd_compare, cmd_question_risk, cmd_run, cmd_score, cmd_threshold
    from tests.run.file_support import put_yaml
    import yaml
    h = finished(tmp_path, monkeypatch)
    cfg = yaml.safe_load((tmp_path / "configs/models/synthetic.yaml").read_text())
    cfg["id"] = "second"
    put_yaml(tmp_path / "configs/models/second.yaml", cfg)
    directory = tmp_path / "results/second/r1/A/klue_mrc_answerable/default"
    args = {**h.args, "model": "configs/models/second.yaml"}
    cmd_run.run(**args, stage="dev", measurer=h, post=h.post)
    cmd_threshold.run(root=tmp_path, run_dir=directory)
    cmd_run.run(**args, stage="test", measurer=h, post=h.post)
    cmd_score.run(root=tmp_path, run_dir=directory)
    cmd_compare.run(root=tmp_path, run_dirs=[h.directory, directory], compare_id="explicit")
    cmd_question_risk.run(root=tmp_path, run_dir=h.directory, history=True)
    result = cmd_report.run(root=tmp_path, run_id="r1", models=["synthetic", "second"], compare_id=["explicit"], out="report.md")
    text = (tmp_path / "report.md").read_text()
    assert result["damaged"] == 0 and result["variants"] == 2
    assert "전체 test 대표 분모" in text and "공통 ok 코호트 F1" in text
    assert "registration.status=exploratory" in text and "primary=True" in text


def test_replay_whitelist_never_emits_path_or_reason(tmp_path, monkeypatch):
    h = finished(tmp_path, monkeypatch)
    run_files.write_json(h.directory / "dev/replay.json", dict(schema="replay/1", source_run_id="old",
        source_code_sha256="a" * 64, source_attempts_sha256="b" * 64, source_fingerprint_sha256="c" * 64,
        source_run_dir="PRIVATE_PATH", reason="PRIVATE_REASON"))
    cmd_report.run(root=tmp_path, run_id="r1", models=["synthetic"], out="report.md")
    text = (tmp_path / "report.md").read_text()
    assert "replay dev: old" in text and "a" * 64 in text and "b" * 64 in text
    assert "PRIVATE_PATH" not in text and "PRIVATE_REASON" not in text


def test_default_report_path_is_results_report_run_id(tmp_path, monkeypatch):
    h = finished(tmp_path, monkeypatch)
    assert cmd_report.run(root=tmp_path, run_id="r1", models=["synthetic"])["ok"]
    assert (tmp_path / "results/_report/r1.md").is_file()
