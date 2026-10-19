"""무엇: 등록 사슬 순수 검사 · 입력: 읽은 증거/개발 재계산 · 출력: 등록 상태 · 계약 판 5 보정 2 §7-4b."""

import math

from jeveval.score.threshold import TAUS

IDENTITY = ("model", "set", "variant", "run_id")


def seal_fields(evidence):
    """질문 임계값 파일을 실행 정체성·fingerprint·범위에 연결한다."""
    a, h = evidence["artifacts"], evidence["hashes"]
    q = a["question_threshold.json"]
    return dict(schema="question_seal/1", **{k: q[k] for k in IDENTITY},
                question_threshold_sha256=h["question_threshold.json"],
                fingerprint_sha256=h["fingerprint.json"], questions=q["questions"], taus=q["taus"])


def _threshold(e):
    a, h = e["artifacts"], e["hashes"]
    q, fp = a["question_threshold.json"], a["fingerprint.json"]
    if q["schema"] != "question_threshold/1" or any(q[k] != fp[k] for k in IDENTITY):
        return False
    if (q["fingerprint_sha256"] != h["fingerprint.json"] or q["manifest"] != e["manifest"] or
            q["manifest_sha256"] != e["manifest_sha256"] or q["dev_final_sha256"] != h["dev/final.jsonl"]):
        return False
    if (q["taus"] != list(TAUS) or q["questions"] != sorted(q["by_question"]) or not q["questions"]):
        return False
    for values in q["by_question"].values():
        if set(values) != set(TAUS):
            return False
        if any(t is not None and (type(t) not in (int, float) or not math.isfinite(t) or not 0 <= t <= 1)
               for t in values.values()):
            return False
    return e["policy"]["status"] == "registered"


def check(evidence, recomputed=None, *, sealed=True):
    """등록 없음과 손상을 구분한다. timestamp를 등록 선후관계 증거로 쓰지 않는다."""
    a = evidence["artifacts"]
    present = evidence["manifest"] is not None or any(n in a for n in
              ("question_threshold.json", "test/question_seal.json"))
    if not present and not evidence["errors"]:
        return "exploratory"
    try:
        if evidence["errors"] or not _threshold(evidence):
            return "registration_damaged"
        if recomputed is not None and recomputed != a["question_threshold.json"]["by_question"]:
            return "registration_damaged"
        if sealed:
            expected, seal = seal_fields(evidence), a["test/question_seal.json"]
            if any(seal.get(k) != v for k, v in expected.items()) or "test/seal.json" not in a:
                return "registration_damaged"
            if a["test/seal.json"].get("dev_final_sha256") != evidence["hashes"]["dev/final.jsonl"]:
                return "registration_damaged"
        return "registered"
    except (KeyError, TypeError, AttributeError, ValueError):
        return "registration_damaged"
