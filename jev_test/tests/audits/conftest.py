"""replay 감사 도구용 합성 실행과 읽기 전용 스크립트 로더."""

from pathlib import Path
import runpy

import pytest

from tests.run.cli_support import Harness


@pytest.fixture
def audit_module():
    root = Path(__file__).resolve().parents[2] / "audits/replay_20261019"
    return lambda name: runpy.run_path(str(root / (name + ".py")))


@pytest.fixture
def audit_h(tmp_path, monkeypatch):
    h = Harness(tmp_path, "fc_call_decision")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("JEV_TEST_KEY", "private-test-key")
    return h
