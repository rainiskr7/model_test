"""합성 overlay 등록 run. 모델 전송은 Harness.post뿐이다."""

import shutil

from jeveval.io.config import read_yaml
from tests.run.cli_support import Harness, REPO
from tests.run.file_support import put_yaml


def registered(tmp_path, monkeypatch):
    h = Harness(tmp_path, "kosgd2", "full")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("JEV_TEST_KEY", "synthetic")
    shutil.copytree(REPO / "configs/analysis", tmp_path / "configs/analysis")
    path = tmp_path / "configs/sets/kosgd2.yaml"
    value = read_yaml(path)
    value["analysis"] = "configs/analysis/question_risk_v2.yaml"
    put_yaml(path, value)
    h.run("dev")
    assert h.command("threshold") == 0
    return h
