"""무엇: 모델 설정 경계 검사 · 입력: 합성 dict · 출력: 오류/누락 · 계약 §8-6 G·J."""

from copy import deepcopy

import pytest

from jeveval.contract.model_config import missing_for_run, validate_model_config
from jeveval.types import ModelConfig


@pytest.fixture
def config():
    return dict(id="m", kind="systemone", served_name="served", base_url="http://127.0.0.1:8000",
                auth_env=None, question_scoring="joint", limit=dict(tokens=100, overflow="reject"),
                input_limit_response=None, encoder=dict(rule="synthetic"),
                tokenizer=dict(path="local", files_sha256={"tokenizer.json": "a" * 64}),
                concurrency=1, b1=None,
                serving=dict(engine=None, engine_version=None, image=None, image_digest=None, command=None),
                repo=dict(id=None, sha=None), t0=dict(status="not_run", record=None), notes="")


@pytest.mark.parametrize("path,value", [
    ("id", "other"), ("kind", "other"), ("kind", []), ("question_scoring", "other"),
    ("concurrency", True), ("concurrency", 0), ("concurrency", 9), ("concurrency", 1.5),
    ("limit.tokens", True), ("limit.tokens", 0), ("limit.tokens", -1),
    ("limit.overflow", "other"), ("encoder.rule", ""), ("served_name", 1),
    ("base_url", "ftp://host"), ("base_url", "http://"), ("base_url", "http://host/v1"),
    ("base_url", "http://host?q=1"), ("base_url", "http://host#x"),
    ("base_url", "http://user:pass@host"), ("base_url", "http://host:99999"),
    ("base_url", "http://host\n"), ("auth_env", "key"), ("auth_env", "A-B"),
    ("auth_env", "1KEY"), ("auth_env", "KEY\n"), ("t0.status", "unknown"),
    ("notes", None), ("b1", {}), ("tokenizer.path", ""),
    ("tokenizer.files_sha256", []), ("tokenizer.files_sha256", {"a/b": "a" * 64}),
    ("tokenizer.files_sha256", {"a\\b": "a" * 64}),
    ("tokenizer.files_sha256", {"x": "A" * 64}),
    ("tokenizer.files_sha256", {"x": "a" * 63}),
    ("tokenizer.files_sha256", {"x": "g" * 64}),
    ("tokenizer.files_sha256", {"..": "a" * 64}),
    ("input_limit_response", {"status": 503, "body_regex": "limit"}),
    ("input_limit_response", {"status": True, "body_regex": "limit"}),
    ("input_limit_response", {"status": 422, "body_regex": "["}),
    ("input_limit_response", {"status": 422, "body_regex": 1}),
])
def test_invalid_values(config, path, value):
    parts = path.split(".")
    target = config if len(parts) == 1 else config[parts[0]]
    target[parts[-1]] = value
    result = validate_model_config(config, "m")
    assert isinstance(result, list) and any(path in error for error in result)


def test_closed_keys_at_every_level(config):
    for path in (None, "limit", "encoder", "tokenizer", "serving", "repo", "t0"):
        original = config if path is None else config[path]
        for key in original:
            data = deepcopy(config)
            target = data if path is None else data[path]
            del target[key]
            assert any("missing key" in e for e in validate_model_config(data, "m"))
        data = deepcopy(config)
        (data if path is None else data[path])["unknown"] = None
        assert any("unknown key" in e for e in validate_model_config(data, "m"))


@pytest.mark.parametrize("value", [None, [], "model", 1])
def test_nonobject(value):
    assert validate_model_config(value, "m") == ["model: expected object"]


@pytest.mark.parametrize("ids", [{"A": True}, {"A": -1}, {"A": 1.5}, {"A": 1, "B": 1}, {"": 0}])
def test_b1_token_values(config, ids):
    config.update(kind="b1", b1={"label_token_ids": ids})
    assert validate_model_config(config, "m") == ["b1.label_token_ids: invalid value"]


def test_conditional_objects_and_regex(config):
    config.update(kind="b1", b1=None)
    assert isinstance(validate_model_config(config, "m"), list)
    for b1 in ({}, {"label_token_ids": None, "extra": 1}):
        config["b1"] = b1
        assert isinstance(validate_model_config(config, "m"), list)
    config.update(kind="systemone", b1=None, input_limit_response={"status": 422})
    assert isinstance(validate_model_config(config, "m"), list)
    config["input_limit_response"]["body_regex"] = "(?i)input.*limit"
    assert isinstance(validate_model_config(config, "m"), ModelConfig)
    config["input_limit_response"]["extra"] = 1
    assert isinstance(validate_model_config(config, "m"), list)


def test_missing_systemone_and_detached_config(config):
    cfg = validate_model_config(config, "m")
    assert missing_for_run(cfg) == []
    config["limit"]["tokens"] = None
    config["tokenizer"]["files_sha256"].clear()
    assert cfg.limit["tokens"] == 100 and cfg.tokenizer["files_sha256"]
    assert missing_for_run(validate_model_config(config, "m")) == ["limit.tokens", "tokenizer.files_sha256"]


def test_missing_b1_exact_label_set(config):
    config.update(kind="b1", b1={"label_token_ids": {"A": 0, "B": 1}})
    cfg = validate_model_config(config, "m")
    assert missing_for_run(cfg, ["B", "A"]) == []
    for labels in (None, [], ["A"], ["A", "B", "C"]):
        assert missing_for_run(cfg, labels) == ["b1.label_token_ids: incomplete"]
    config["b1"]["label_token_ids"] = None
    assert missing_for_run(validate_model_config(config, "m"), ["A", "B"]) == [
        "b1.label_token_ids", "b1.label_token_ids: incomplete"]
    config["b1"]["label_token_ids"] = {}
    assert missing_for_run(validate_model_config(config, "m"), ["A", "B"]) == ["b1.label_token_ids: incomplete"]
