"""무엇: T0 통과 증거 순수 검사 · 입력: 설정/변조 기록 · 출력: 거부 사유 · 계약 T-i."""

from copy import deepcopy
from hashlib import sha256

import pytest

from jeveval.t0.gate import check_record
from jeveval.t0.record import config_sha256
from jeveval.t0.request import canonical_bytes


def evidence():
    cfg = dict(id="m", serving={"version":"1"}, t0={"status":"passed", "record":None})
    payload = canonical_bytes(dict(status="PASS", config_sha256=config_sha256(cfg)))
    cfg["t0"]["record"] = dict(path="record.json", sha256=sha256(payload).hexdigest())
    return cfg, payload


def test_exact_record_and_not_passed_bypass():
    cfg, payload = evidence()
    before = deepcopy(cfg)
    assert check_record(cfg, payload) == [] and cfg == before
    for status in ("partial", "not_run"):
        cfg["t0"] = dict(status=status, record=None)
        assert check_record(cfg, None) == []


def test_missing_hash_status_and_config_mismatch():
    cfg, payload = evidence()
    assert check_record(cfg, None) == ["t0_record_missing"]
    assert check_record(cfg, payload + b" ") == ["t0_record_sha256"]
    cfg["serving"]["version"] = "2"
    assert check_record(cfg, payload) == ["t0_record_config_sha256"]
    payload = canonical_bytes(dict(status="FAIL", config_sha256=config_sha256(cfg)))
    cfg["t0"]["record"]["sha256"] = sha256(payload).hexdigest()
    assert check_record(cfg, payload) == ["t0_record_status"]


@pytest.mark.parametrize("payload", [b"null", b"[]", b"invalid", b' {"status":"FAIL","status":"PASS"}', b"\xff"])
def test_invalid_record_json(payload):
    cfg, _ = evidence()
    cfg["t0"]["record"]["sha256"] = sha256(payload).hexdigest()
    assert check_record(cfg, payload) == ["t0_record_json"]
