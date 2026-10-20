"""무엇: 봉인 여섯 fixture의 실제 인증 명령 · 입력: 기존 바이트 · 출력: a/b/c/종료값 · 계약 §5-7."""

from datetime import datetime
import json
import os

import pytest

from jeveval.io import run_files
from jeveval.run import context
from jeveval.io.hashes import sha256_file
from jeveval.io.splits import write_split_plan
from jeveval.run import cli
from jeveval.run.fingerprint import build_fingerprint
from jeveval.run.layout import run_dir
from jeveval.types import BoundQuestion, Item
from tests.run.cli_support import Harness, REPO
from tests.run.file_support import put_yaml, output_files
from tests.run.stage_support import install_case, plan_for

CASES = json.loads((REPO / "tests/fixtures/seal/cases.json").read_text())["cases"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["name"])
def test_all_seal_fixtures_through_cli(tmp_path, monkeypatch, capsys, case):
    Harness(tmp_path)
    put_yaml(tmp_path / "configs/datasets.yaml", {"sets": [{"id": "synthetic"}]})
    put_yaml(tmp_path / "configs/splits/rules.yaml", {"sets": {"synthetic": {}}})
    task_path = "configs/tasks/synthetic.yaml"
    put_yaml(tmp_path / task_path, dict(set="synthetic", variant="full", state={"kind": "plain_text"},
        questions=[dict(id="ready", role="success", type="noul", instructions="ready?",
            criteria={"true": "yes", "false": "no"}, label="fixture")],
        per_item_questions=None, group_key="context"))
    write_split_plan(plan_for(), tmp_path / "configs/splits/synthetic.json")
    data = tmp_path / "dataset/synthetic"
    data.mkdir()
    (data / "source").write_text("synthetic source")
    (data / "SHA256SUMS").write_text(sha256_file(data / "source") + "  source\n")
    directory = run_dir(tmp_path / "results", "synthetic", "r1", "synthetic", "full")
    directory.mkdir(parents=True)
    fp = build_fingerprint(root=tmp_path, run_id="r1", model_cfg_path="configs/models/synthetic.yaml",
        task_path=task_path, set_name="synthetic", variant="full", started_at="start")
    run_files.write_json(directory / "fingerprint.json", fp)
    install_case(directory, case, sealed=True)
    run_files.write_json(directory / "risk.json", dict(schema="risk/1", model="synthetic", set="synthetic",
        variant="full", run_id="r1", threshold_sha256=case["risk_threshold_sha256"]))
    if case["threshold_raw"] is not None:
        mtime = (datetime.fromisoformat(case["seal"]["sealed_at"]).timestamp()
                 + case["threshold_mtime"] - case["test_start_mtime"])
        os.utime(directory / "threshold.json", (mtime, mtime))
    question = BoundQuestion("ready", "success", "noul", "ready?", None,
                            {"true": "yes", "false": "no"}, "fixture", case["gold"]["ready"])
    item = Item("synthetic", "g", "ok", "synthetic", [question], {}, None)
    def load(**kwargs):
        assert kwargs["stage"] == "dev"
        return [item]
    # fixture는 synthetic 셋이라 원본 어댑터만 주입한다. fingerprint/완료/outcome/재계산은 실제다.
    monkeypatch.setattr(context, "load_items", load)
    monkeypatch.chdir(tmp_path)
    before = output_files(directory)
    code = cli.main(["certify", "--run-dir", str(directory)])
    result = json.loads(capsys.readouterr().out)
    assert (code == 0) == case["expected"]["certify"]
    if case["expected"]["checks"] is not None:
        assert result["checks"] == case["expected"]["checks"]
        assert ("threshold_mtime_after_seal" in result["warnings"]) == case["expected"]["mtime_warning"]
    assert output_files(directory) == before
