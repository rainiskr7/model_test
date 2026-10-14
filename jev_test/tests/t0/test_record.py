"""무엇: 원문 없는 결과·순환 없는 config 해시 · 입력: 실제 판정 · 출력: 정규 기록 · 계약 T-h."""

from copy import deepcopy

import pytest

from jeveval.t0.judge import judge
from jeveval.t0.record import build_record, config_sha256
from jeveval.t0.request import canonical_bytes
from jeveval.types.t0 import T0Judgement


def test_config_hash_excludes_only_t0():
    cfg = dict(model="x", serving={"image":"i","version":"v"}, t0={"status":"not_run"})
    original = config_sha256(cfg)
    cfg["t0"] = {"status":"passed","record":{"path":"p","sha256":"a" * 64}}
    assert config_sha256(cfg) == original
    reordered = {k: cfg[k] for k in reversed(cfg)}
    reordered["serving"] = {"version":"v","image":"i"}
    assert config_sha256(reordered) == original
    cfg["serving"]["version"] = "changed"
    assert config_sha256(cfg) != original


def test_result_contains_no_source_and_roundtrips(scenario):
    case, obs, tolerances = scenario
    result = judge([case], [obs], [obs], tolerances, inputs_sha256="a" * 64,
                   reference_epsilon=5e-5, server_epsilon=5e-5)
    assert T0Judgement.from_dict(result.to_dict()) == result
    cfg = dict(notes="PRIVATE_CONFIG", t0={"status":"not_run"})
    temperature = dict(path="fake", status="PASS", evidence_sha256="c" * 64)
    before = deepcopy((result, cfg, temperature))
    args = dict(model="model", run_id="r1", model_yaml_dict=cfg, judgement=result,
                inputs_sha256="a" * 64, tolerance_sha256="b" * 64, temperature=temperature)
    record = build_record(**args)
    raw = canonical_bytes(record, sort_keys=True)
    assert record["config_sha256"] == config_sha256(cfg)
    assert len(record["detection_scope"]) == 2 and record["temperature"]["path"] == "fake"
    assert all(word.encode() not in raw for word in ("private state", "PRIVATE_CONFIG", "매우 낮음", "고르시오"))
    assert (result, cfg, temperature) == before and canonical_bytes(build_record(**args), sort_keys=True) == raw
    args["temperature"] = dict(path="real", status="NOT_RUN", evidence_sha256=None)
    assert build_record(**args)["temperature"]["status"] == "NOT_RUN"
    args["temperature"]["status"] = "PASS"
    with pytest.raises(ValueError):
        build_record(**args)
