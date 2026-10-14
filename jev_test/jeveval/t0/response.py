"""무엇: 세 종류 T0 응답 검증 · 입력: 원 JSON/질문/반올림 반단위 · 출력: Validated · 계약 §8-7 T-b."""

import json
import math

from jeveval.contract.response import validate_response as validate_standard
from jeveval.types import Request, Validated
from jeveval.t0.distribution import nonnegative

REASONS = ("type_mismatch", "noul_value", "choice_keys", "choice_values", "choice_pick",
           "score_keys", "score_values", "score_legend", "score_confidence", "score_value", "unknown_rounding")


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _probability(value):
    return nonnegative(value) and value <= 1


def _score_reason(answer, question, epsilon_r):
    levels = {str(i): text for i, text in enumerate(question["criteria"])}
    probs = answer.get("probabilities")
    if not isinstance(probs, dict) or probs.keys() != levels.keys():
        return "score_keys"
    if (any(not _probability(p) for p in probs.values())
            or abs(math.fsum(probs.values()) - 1) > len(levels) * 5e-5 + 1e-9):
        return "score_values"
    if answer.get("legend") != levels:
        return "score_legend"
    confidence, score = answer.get("confidence"), answer.get("score")
    if not _probability(confidence):
        return "score_confidence"
    if not nonnegative(score) or score > len(levels) - 1:
        return "score_value"
    if epsilon_r is None:
        return "unknown_rounding"
    if abs(confidence - max(probs.values())) > epsilon_r + 1e-9:
        return "score_confidence"
    weighted = math.fsum(i * probs[str(i)] for i in range(len(levels)))
    if abs(score - weighted) > epsilon_r * (1 + sum(range(len(levels)))) + 1e-9:
        return "score_value"
    return None


def _types(answers, questions, warnings):
    for qid, question in questions.items():
        answer = answers[qid]
        if not isinstance(answer, dict):
            return "type_mismatch"
        allowed = {"type", "noul"} if question["type"] == "noul" else (
            {"type", "score", "legend", "confidence", "probabilities"} if question["type"] == "score"
            else {"type", "choice", "confidence", "probabilities"})
        if answer.keys() - allowed and "extra_keys" not in warnings:
            warnings.append("extra_keys")
        if answer.get("type") != question["type"]:
            return "type_mismatch"
    return None


def _values(answers, questions, epsilon_r):
    reasons = []
    for qid, question in questions.items():
        if question["type"] == "score":
            reason = _score_reason(answers[qid], question, epsilon_r)
        else:
            raw = json.dumps({"answers": {qid: answers[qid]}})
            reason = validate_standard(raw, Request("t0", "t0", {qid: question})).reason
        if reason:
            reasons.append(reason)
    if epsilon_r is None:
        reasons.append("unknown_rounding")
    return min(reasons, key=REASONS.index) if reasons else None


def validate_response(raw, questions, epsilon_r):
    """§3-1 전역 단계 우선순위 뒤 score 단계를 검사. 미확인 정책도 답을 노출하지 않는다."""
    if epsilon_r is not None and not nonnegative(epsilon_r):
        raise ValueError("invalid rounding half-unit")
    warnings = []
    try:
        body = json.loads(raw, object_pairs_hook=_unique)
    except (ValueError, TypeError, UnicodeError):
        return Validated("bad_body", warnings, None)
    if not isinstance(body, dict):
        return Validated("bad_body", warnings, None)
    # 공개 진입점으로 봉투 경고를 얻는다. qid 검사 전에도 usage 경고를 보존한다.
    envelope = {**body, "answers": {"q": {"type": "noul", "noul": 0}}}
    warnings.extend(validate_standard(json.dumps(envelope), Request("t0", "t0", {"q": {"type": "noul"}})).warnings)
    if not isinstance(body.get("answers"), dict):
        return Validated("bad_body", warnings, None)
    answers = body["answers"]
    if answers.keys() != questions.keys():
        return Validated("qid_mismatch", warnings, None)
    reason = _types(answers, questions, warnings)
    if reason is None:
        reason = _values(answers, questions, epsilon_r)
    return Validated(reason, warnings, answers if reason is None else None)
