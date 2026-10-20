"""무엇: 파생 실행 순서 · 입력: 합성 KoSGD full/actions · 출력: 자체 봉인/0비용 · 계약 §5-4."""

import pytest

from jeveval.io import records, run_files
from jeveval.io.config import load_taskspec
from jeveval.run.fingerprint import build_fingerprint
from tests.run.cli_support import Harness
from tests.run.file_support import output_files, put_yaml


@pytest.mark.parametrize("kind", ["systemone", "b1"])
def test_derived_stages_require_own_threshold_and_keep_full_bytes(tmp_path, monkeypatch, kind):
    h = Harness(tmp_path, "kosgd", "full", kind)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("JEV_TEST_KEY", "key")
    h.finish()
    source, before, sent = h.directory, output_files(h.directory), len(h.sent)
    h.variant = "actions_only"
    assert h.run("dev")["derived"]
    derived_before = output_files(h.directory)
    with pytest.raises(ValueError):
        h.run("test")
    assert output_files(h.directory) == derived_before
    assert h.command("threshold") == 0
    assert h.run("test")["derived"]
    assert h.command("score") == h.command("certify") == 0
    assert len(h.sent) == sent and output_files(source) == before
    assert not (h.directory / "summary.json").exists()
    for stage, cost in run_files.read_json(h.directory / "scores.json")["cost"]["by_stage"].items():
        assert cost["n_calls"] == cost["n_attempts"] == cost["input_tokens"]["sum"] == 0
        assert cost["derived_from"] == source.relative_to(tmp_path).as_posix()
        assert cost["latency_ms"]["p50"] is None
        finals, _ = records.read_finals(h.directory / stage / "final.jsonl")
        assert len(finals[0].calls) == (10 if kind == "b1" else 1)
        assert {qid for c in finals[0].calls for qid in c.answers_parsed} == {
            q.id for q in load_taskspec(
                tmp_path / "configs/tasks/kosgd_actions_only.yaml").questions}
    before = output_files(h.directory)
    h.run("test")
    assert output_files(h.directory) == before
    run_files.write_json(h.directory / "summary.json", {"stale": True})
    before = output_files(h.directory)
    assert h.command("score") == 1
    assert output_files(h.directory) == before


@pytest.mark.parametrize("failure", ["incomplete", "model_changed", "source_fingerprint", "marker", "other_model_path"])
def test_derived_source_rejection_before_gate(tmp_path, monkeypatch, failure):
    h = Harness(tmp_path, "kosgd", "full")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("JEV_TEST_KEY", "key")
    h.run("dev")
    source = h.directory
    if failure == "incomplete":
        (source / "dev/final.jsonl").write_text("")
    elif failure == "model_changed":
        import yaml
        path = tmp_path / h.args["model"]
        cfg = yaml.safe_load(path.read_text())
        cfg["served_name"] = "different"
        put_yaml(path, cfg)
    elif failure == "source_fingerprint":
        fp = run_files.read_json(source / "fingerprint.json")
        fp["code_sha256"] = "changed"
        run_files.write_json(source / "fingerprint.json", fp)
    elif failure == "other_model_path":
        path = tmp_path / "configs/alternate/synthetic.yaml"
        path.parent.mkdir()
        path.write_bytes((tmp_path / h.args["model"]).read_bytes())
        fp = build_fingerprint(root=tmp_path, model_cfg_path=path, task_path=h.args["task"],
                               run_id="r1", set_name="kosgd", variant="full", started_at="start")
        run_files.write_json(source / "fingerprint.json", fp)
    h.variant = "actions_only"
    if failure == "marker":
        h.run("dev")
        run_files.write_json(h.directory / "dev/derived.json", {"derived_from": "wrong"})
        with (h.directory / "dev/final.jsonl").open("a") as stream:
            stream.write('{"broken":')
    before = output_files(tmp_path / "results")
    with pytest.raises(ValueError):
        h.run("dev")
    assert output_files(tmp_path / "results") == before
