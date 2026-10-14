"""무엇: 본시험 전 T0 게이트/동결 · 입력: 임시 YAML/증거 · 출력: 선행 거부/재개 거부 · 계약 T-i."""

from hashlib import sha256
import json

import pytest
import yaml

from jeveval.contract.model_config import validate_model_config
from jeveval.io import run_files
from jeveval.run import cmd_run
from tests.run.cli_support import Harness, output_files, put_yaml
from tests.run.t0_support import passed_record


@pytest.fixture
def h(tmp_path, monkeypatch):
    harness = Harness(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("JEV_TEST_KEY", "test")
    return harness


def prepare(h):
    path = h.root / h.args["model"]
    cfg = yaml.safe_load(path.read_text())
    record = passed_record(h.root, cfg)
    put_yaml(path, cfg)
    return path, cfg, record


@pytest.mark.parametrize("defect", ["missing", "sha", "status", "config", "json", "escape"])
def test_record_checked_before_loading_or_writing(h, monkeypatch, defect):
    path, cfg, record = prepare(h)
    if defect == "missing":
        record.unlink()
    elif defect == "sha":
        record.write_bytes(record.read_bytes() + b" ")
    elif defect == "config":
        cfg["serving"]["engine_version"] = "changed"
    elif defect == "escape":
        record.unlink()
        record.symlink_to(h.root.parent / "reranker_test/evalcommon/schema.py")
        cfg["t0"]["record"]["sha256"] = sha256(record.read_bytes()).hexdigest()
    else:
        data = json.loads(record.read_bytes())
        data["status"] = "FAIL"
        record.write_text(json.dumps(data) if defect == "status" else "invalid")
        cfg["t0"]["record"]["sha256"] = sha256(record.read_bytes()).hexdigest()
    put_yaml(path, cfg)
    def forbidden(*args, **kwargs):
        raise AssertionError("must not load inputs before T0 gate")
    monkeypatch.setattr(cmd_run.stage_inputs, "load_items", forbidden)
    before = output_files(h.root)
    with pytest.raises(ValueError, match="T0"):
        h.run("dev")
    assert output_files(h.root) == before and not h.sent


def test_passed_record_uses_yaml_before_base_url_override(h):
    prepare(h)
    assert h.run("dev", base_url="http://127.0.0.1:9")["ok"]
    assert h.sent[0][0].startswith("http://127.0.0.1:9/")
    fp = run_files.read_json(h.directory / "fingerprint.json")
    assert "external" in fp and "env" in fp


def test_late_status_change_rejects_resume(h):
    h.run("dev")
    prepare(h)
    before, sent = output_files(h.root), len(h.sent)
    with pytest.raises(ValueError):
        h.run("dev")
    assert output_files(h.root) == before and len(h.sent) == sent


@pytest.mark.parametrize("record", [None, "path", {}, {"path":"p"},
    {"path":"p","sha256":"bad"}, {"path":"../p","sha256":"a" * 64},
    {"path":"/p","sha256":"a" * 64}, {"path":"p","sha256":"a" * 64,"extra":1}])
def test_passed_structure_is_required(h, record):
    path = h.root / h.args["model"]
    cfg = yaml.safe_load(path.read_text())
    cfg["t0"] = dict(status="passed", record=record)
    assert "t0.record: expected path and sha256" in validate_model_config(cfg, "synthetic")
