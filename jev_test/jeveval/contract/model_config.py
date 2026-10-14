"""무엇: 모델 설정 검사 · 입력: YAML 객체·stem · 출력: ModelConfig/오류 · 계약 §8-6 G·J."""

import re
from pathlib import PurePosixPath
from urllib.parse import urlsplit

from jeveval.types import ModelConfig


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _nullable(check):
    return lambda value: value is None or check(value)


def _filename(value):
    return _text(value) and value not in (".", "..") and not any(c in value for c in "/\\\x00")


def _hashes(value):
    return isinstance(value, dict) and all(
        _filename(name) and isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest)
        for name, digest in value.items())


def _token_ids(value):
    return (isinstance(value, dict)
            and all(_text(k) and type(v) is int and v >= 0 for k, v in value.items())
            and len(set(value.values())) == len(value))


def _base_url(value):
    if not isinstance(value, str) or not value.startswith(("http://", "https://")):
        return False
    try:
        parts = urlsplit(value)
        return (bool(parts.hostname) and not parts.path and not parts.query and not parts.fragment
                and parts.username is None and parts.password is None
                and (parts.port is None or parts.port > 0)
                and not any(c.isspace() or ord(c) < 32 for c in value)
                and "?" not in value and "#" not in value)
    except ValueError:
        return False


def _regex(value):
    if not isinstance(value, str):
        return False
    try:
        re.compile(value)
        return True
    except re.error:
        return False


def valid_t0_record(value):
    """passed 증거는 저장소 상대 경로와 SHA-256만 갖는다 (§8-7 T-i)."""
    if not isinstance(value, dict) or set(value) != {"path", "sha256"}:
        return False
    path, digest = value["path"], value["sha256"]
    if not _text(path) or "\\" in path or "\x00" in path:
        return False
    relative = PurePosixPath(path)
    return (not relative.is_absolute() and ".." not in relative.parts and path != "."
            and relative.as_posix() == path and isinstance(digest, str)
            and re.fullmatch(r"[0-9a-f]{64}", digest) is not None)


def _object(data, schema, prefix, errors):
    """중첩 닫힌 키와 값의 오류를 경로별로 모은다."""
    if not isinstance(data, dict):
        errors.append(f"{prefix or 'model'}: expected object")
        return
    for key in data:
        if key not in schema:
            errors.append(f"{prefix}{key}: unknown key")
    for key, check in schema.items():
        path = prefix + key
        if key not in data:
            errors.append(f"{path}: missing key")
        elif isinstance(check, dict):
            _object(data[key], check, path + ".", errors)
        elif not check(data[key]):
            errors.append(f"{path}: invalid value")


def validate_model_config(data: dict, file_stem: str) -> ModelConfig | list[str]:
    """P0의 null은 보존하되 구조·enum·실제 값은 검사한다. 입출력은 하지 않는다."""
    text = _nullable(_text)
    schema = {
        "id": lambda v: _text(v) and v == file_stem,
        "kind": lambda v: v in ("systemone", "b1"),
        "served_name": text, "base_url": _nullable(_base_url),
        "auth_env": _nullable(lambda v: isinstance(v, str) and re.fullmatch(r"[A-Z_][A-Z0-9_]*", v)),
        "question_scoring": lambda v: v in ("joint", "separate"),
        "limit": {"tokens": _nullable(lambda v: type(v) is int and v > 0),
                  "overflow": _nullable(lambda v: v in ("truncate_tail", "reject"))},
        "input_limit_response": lambda v: v is None or isinstance(v, dict),
        "encoder": {"rule": text},
        "tokenizer": {"path": text, "files_sha256": _nullable(_hashes)},
        "concurrency": lambda v: type(v) is int and 1 <= v <= 8,
        "b1": lambda v: v is None or isinstance(v, dict),
        "serving": dict.fromkeys(("engine", "engine_version", "image", "image_digest", "command"), text),
        "repo": {"id": text, "sha": text},
        "t0": {"status": lambda v: v in ("not_run", "partial", "passed"), "record": lambda v: True},
        "notes": lambda v: isinstance(v, str),
    }
    errors = []
    _object(data, schema, "", errors)
    if isinstance(data, dict):
        t0 = data.get("t0")
        if isinstance(t0, dict) and t0.get("status") == "passed" and not valid_t0_record(t0.get("record")):
            errors.append("t0.record: expected path and sha256")
        if isinstance(data.get("input_limit_response"), dict):
            _object(data["input_limit_response"], {"status": lambda v: type(v) is int and v in (400, 422),
                    "body_regex": _regex}, "input_limit_response.", errors)
        if data.get("kind") == "b1":
            _object(data.get("b1"), {"label_token_ids": _nullable(_token_ids)}, "b1.", errors)
        elif data.get("kind") == "systemone" and data.get("b1") is not None:
            errors.append("b1: expected null for systemone")
    if errors:
        return errors
    try:
        return ModelConfig.from_dict(data)
    except (TypeError, ValueError):
        return ["model: expected JSON-compatible field values"]


def missing_for_run(cfg: ModelConfig, b1_labels: list[str] | None = None) -> list[str]:
    """실행 전 누락 목록. B1 라벨 집합이 없으면 완전하다고 판정하지 않는다 (§8-6 J)."""
    required = {"served_name": cfg.served_name, "base_url": cfg.base_url,
                "limit.tokens": cfg.limit["tokens"], "limit.overflow": cfg.limit["overflow"],
                "encoder.rule": cfg.encoder["rule"], "tokenizer.path": cfg.tokenizer["path"]}
    missing = [path for path, value in required.items() if value is None]
    if not cfg.tokenizer["files_sha256"]:
        missing.append("tokenizer.files_sha256")
    if cfg.kind == "b1":
        ids = cfg.b1["label_token_ids"]
        if ids is None:
            missing.append("b1.label_token_ids")
        if b1_labels is None or ids is None or set(ids) != set(b1_labels):
            missing.append("b1.label_token_ids: incomplete")
    return missing
