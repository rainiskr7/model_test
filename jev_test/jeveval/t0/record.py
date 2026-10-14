"""무엇: 원문 없는 T0 기록 · 입력: 순수 판정/설정/C1 증거 · 출력: 정규 dict · 계약 §8-7 T-h."""

from hashlib import sha256
import re

from jeveval.t0.request import canonical_bytes
from jeveval.types.t0 import T0Judgement

DETECTION_SCOPE = {
    "t0": "고정 입력의 참조/서버 분포·답 대조; 허용폭 이하 temperature 오류는 검출을 보장하지 않음",
    "c1_temperature": "고정 logit의 temperature 1회 경로 검사; fake는 실제 참조/서버 경로의 증거가 아님",
}


def config_sha256(model_yaml_dict):
    """결과 포인터 t0만 제외하며 키 순서와 무관한 정규 설정 바이트를 해시한다."""
    return sha256(canonical_bytes({k: v for k, v in model_yaml_dict.items() if k != "t0"}, sort_keys=True)).hexdigest()


def _digest(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def build_record(*, model, run_id, model_yaml_dict, judgement: T0Judgement,
                 inputs_sha256, tolerance_sha256, temperature):
    """허용된 증거 필드만 복사한다. 원 요청·원 응답·설정 본문은 기록에 넣지 않는다."""
    if not all(isinstance(s, str) and s for s in (model, run_id)):
        raise ValueError("model/run IDs required")
    if judgement.status not in ("PASS", "FAIL", "INCOMPLETE", "PARTIAL"):
        raise ValueError("invalid T0 judgement")
    if not _digest(inputs_sha256) or not _digest(tolerance_sha256):
        raise ValueError("invalid evidence digest")
    if (not isinstance(temperature, dict) or set(temperature) != {"path", "status", "evidence_sha256"}
            or temperature["path"] not in ("real", "fake")
            or temperature["status"] not in ("PASS", "FAIL", "INCOMPLETE", "NOT_RUN")
            or (temperature["evidence_sha256"] is not None and not _digest(temperature["evidence_sha256"]))
            or (temperature["status"] in ("PASS", "FAIL") and temperature["evidence_sha256"] is None)):
        raise ValueError("invalid temperature evidence")
    value = dict(schema="t0/1", model=model, run_id=run_id, **judgement.to_dict(),
        config_sha256=config_sha256(model_yaml_dict), inputs_sha256=inputs_sha256,
        tolerance_sha256=tolerance_sha256, detection_scope=dict(DETECTION_SCOPE), temperature=dict(temperature))
    canonical_bytes(value, sort_keys=True)
    return value
