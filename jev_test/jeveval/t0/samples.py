"""무엇: T0 대상 해시·관측 봉투 · 입력: 확정 입력/원응답 · 출력: 단계 레코드 · 계약 §8-7 T-a/d."""

from hashlib import sha256

from jeveval.t0.request import canonical_bytes
from jeveval.types.t0 import T0Observation


def targets(row):
    body = row.reference_body
    return {qid: sha256(canonical_bytes(dict(state=body["state"], question=question,
                                            images=body.get("images", [])))).hexdigest()
            for qid, question in body["questions"].items()}


def observation(row, inputs_sha256, status, raw, *, reference=False, error=None, length_status=None):
    return T0Observation(row.case_id, inputs_sha256, row.request_sha256,
        row.reference_envelope_sha256 if reference else row.envelope_sha256,
        status, raw, error, length_status)
