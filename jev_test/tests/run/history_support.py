"""무엇: 역사 보고 합성 실행 · 입력: tmp_path · 출력: 완료 Harness · 계약 §9."""

import shutil

from tests.run.cli_support import Harness, REPO


def finished(tmp_path, monkeypatch, set_name="klue_mrc_answerable", variant="default"):
    h = Harness(tmp_path, set_name, variant)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("JEV_TEST_KEY", "synthetic-key")
    shutil.copytree(REPO / "configs/analysis", tmp_path / "configs/analysis")
    h.finish()
    return h
