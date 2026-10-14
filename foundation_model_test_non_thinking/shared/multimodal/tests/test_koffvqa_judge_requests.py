"""API judge pre-refactor anchors; variable fields are listed in _r3_runner_fakes."""

from openpyxl import Workbook

from shared.multimodal.tests._runner_fakes import load_runner, read_json
from shared.multimodal.tests._r3_runner_fakes import assert_capture, capture, cli, prepare_local


def test_main_requests_storage_identity(monkeypatch, tmp_path, capsys, fresh_import):
    runner = load_runner(fresh_import, "koffvqa_api_judge")
    predfile = tmp_path / "synthetic.xlsx"
    book = Workbook()
    sheet = book.active
    sheet.append(["index", "question", "answer", "prediction"])
    sheet.append(["one", "질문", "루브릭", "응답"])
    sheet.append(["two", "질문2", "기준2", "응답2"])
    book.save(predfile)
    state = prepare_local(monkeypatch, tmp_path, ['{"score": 8, "reason": "충족"}', "no JSON"])
    cli(monkeypatch, ["--predfile", str(predfile), "--target-model", "target", "--judge-model", "alias",
                      "--judge-base-url", "http://unused.invalid/v1/chat/completions", "--judge-api-key", "synthetic-key",
                      "--seed", "7", "--judge-max-tokens", "37"])
    assert runner.main() is None
    output = tmp_path / "results/target/r3-session/vision/multimodal/koffvqa_api_judge"
    summary = read_json(output / "summary.json")
    assert summary["judge_served_identity"] == {"model": ["served"], "system_fingerprint": ["fp"], "provider": ["provider"]}
    assert (summary["total"], summary["scored"], summary["avg_score"]) == (2, 1, 8.0)
    assert_capture("koffvqa_judge", capture(output, None, state, capsys), tmp_path)
