"""KOFFVQA pre-refactor anchors; variable fields are listed in _r3_runner_fakes."""

import base64
import csv
import io

from shared.multimodal.tests._runner_fakes import assert_requests, forbidden, load_runner, png, read_json
from shared.multimodal.tests._r3_runner_fakes import arguments, assert_capture, capture, cli, prepare_local


def test_main_resume_merge_and_no_resume(monkeypatch, tmp_path, capsys, fresh_import):
    runner = load_runner(fresh_import, "koffvqa_run")
    buf = io.BytesIO()
    png("red").save(buf, format="PNG")
    tsv = tmp_path / "synthetic.tsv"
    with tsv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["index", "question", "image", "answer", "category", "l2-category"])
        for i in range(2):
            writer.writerow([i, f"질문 {i}", base64.b64encode(buf.getvalue()).decode(), "루브릭", "table", "세부"])
    monkeypatch.setattr(runner.requests, "get", forbidden)
    output = tmp_path / "results/test_model_a_1/r3-session/vision/multimodal/koffvqa_run"
    output = output.with_name("koffvqa")
    captures = []
    first = None
    for responses, extra, rc_expected, prompts in [
        (["첫 응답", ValueError("invalid request")], [], 1, ["질문 0", "질문 1"]),
        (["재시도 응답"], [], 1, ["질문 1"]),
        (["새 응답 0", "새 응답 1"], ["--no-resume"], 1, ["질문 0", "질문 1"]),
    ]:
        with monkeypatch.context() as patch:
            state = prepare_local(patch, tmp_path, responses)
            cli(patch, arguments("--data", str(tsv), "--limit", "2", *extra))
            rc = runner.main()
            assert rc == rc_expected
            assert_requests(state, prompts, [(255, 0, 0)] * len(prompts))
            records = read_json(output / "results.json")
            if len(prompts) == 1:
                assert records[0] == first
                assert records[1]["prediction"] == "재시도 응답"
            first = records[0]
            captures.append(capture(output, rc, state, capsys))
    assert_capture("koffvqa_resume", captures, tmp_path)
