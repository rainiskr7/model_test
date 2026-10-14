"""무엇: 본시험 T0 증거 순수 검사 · 입력: 모델 YAML/기록 바이트 · 출력: 오류 목록 · 계약 §8-7 T-i."""

from hashlib import sha256
import json

from jeveval.contract.model_config import valid_t0_record
from jeveval.t0.record import config_sha256


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate record key")
        result[key] = value
    return result


def check_record(model_yaml_dict, payload: bytes | None):
    """passed 아닌 설정은 기존 실행을 유지한다. 원문/예외 내용은 오류에 넣지 않는다."""
    t0 = model_yaml_dict["t0"]
    if t0["status"] != "passed":
        return []
    if not valid_t0_record(t0["record"]):
        return ["t0_record_structure"]
    if payload is None:
        return ["t0_record_missing"]
    if sha256(payload).hexdigest() != t0["record"]["sha256"]:
        return ["t0_record_sha256"]
    try:
        record = json.loads(payload, object_pairs_hook=_unique)
        json.dumps(record, allow_nan=False)
    except (ValueError, TypeError, UnicodeError):
        return ["t0_record_json"]
    if not isinstance(record, dict):
        return ["t0_record_json"]
    errors = []
    if record.get("status") != "PASS":
        errors.append("t0_record_status")
    if record.get("config_sha256") != config_sha256(model_yaml_dict):
        errors.append("t0_record_config_sha256")
    return errors
