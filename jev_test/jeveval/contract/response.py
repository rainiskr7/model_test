"""무엇: systemone 응답 검증 · 입력: 응답 원문·요청 · 출력: Validated · 계약 §3-1."""

import json
import math

from jeveval.types import Request, Validated


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _finite(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _probability(value):
    return _finite(value) and 0 <= value <= 1


def _warn(warnings, name):
    if name not in warnings:
        warnings.append(name)


def _body_warnings(body, warnings):
    for key, value in body.items():
        if key != "answers":
            _warn(warnings, "extra_keys")
        if key == "usage" and value is not None:
            if not isinstance(value, dict) or type(value.get("input_tokens")) is not int:
                _warn(warnings, "usage_input_tokens_invalid")


def _type_reason(answers, questions, warnings):
    for qid, question in questions.items():
        answer = answers[qid]
        if not isinstance(answer, dict):
            return "type_mismatch"
        allowed = {"type", "noul"} if question["type"] == "noul" else {
            "type", "choice", "confidence", "probabilities"}
        if answer.keys() - allowed:
            _warn(warnings, "extra_keys")
        if answer.get("type") != question["type"]:
            return "type_mismatch"
    return None


def _choice_pick(answer):
    choice, confidence = answer.get("choice"), answer.get("confidence")
    return (isinstance(choice, str) and choice in answer["probabilities"]
            and _finite(confidence)
            and abs(confidence - answer["probabilities"][choice]) <= 1e-9)


def _value_reason(answers, questions):
    nouls = [answers[qid] for qid, q in questions.items() if q["type"] == "noul"]
    choices = [(answers[qid], q) for qid, q in questions.items() if q["type"] == "choice"]
    if any(not _probability(a.get("noul")) for a in nouls):
        return "noul_value"
    for answer, question in choices:
        probs = answer.get("probabilities")
        if not isinstance(probs, dict) or probs.keys() != question["criteria"].keys():
            return "choice_keys"
    for answer, _ in choices:
        probs = answer["probabilities"]
        if (any(not _probability(p) for p in probs.values())
                or abs(math.fsum(probs.values()) - 1) > len(probs) * 5e-5 + 1e-9):
            return "choice_values"
    if any(not _choice_pick(answer) for answer, _ in choices):
        return "choice_pick"
    return None


def validate_response(raw: str | bytes, request: Request) -> Validated:
    """각 검사 단계를 전체 질문에 적용하여 질문 순서보다 사유 우선순위를 지킨다."""
    if any(q["type"] == "score" for q in request.questions.values()):
        raise NotImplementedError("score is out of scope")
    warnings = []
    try:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        body = json.loads(raw, object_pairs_hook=_unique_object)
    except (ValueError, TypeError):
        return Validated("bad_body", warnings, None)
    if not isinstance(body, dict):
        return Validated("bad_body", warnings, None)
    _body_warnings(body, warnings)
    answers = body.get("answers")
    if not isinstance(answers, dict):
        return Validated("bad_body", warnings, None)
    if answers.keys() != request.questions.keys():
        return Validated("qid_mismatch", warnings, None)
    reason = _type_reason(answers, request.questions, warnings)
    if reason is None:
        reason = _value_reason(answers, request.questions)
    return Validated(reason, warnings, answers if reason is None else None)


def read_usage(raw: str | bytes) -> tuple[dict | None, list[str]]:
    """답 검증과 독립적으로 systemone 입력 토큰을 추출한다 (§5-5b 보정 9b)."""
    try:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        body = json.loads(raw, object_pairs_hook=_unique_object)
    except (ValueError, TypeError):
        return None, []
    if not isinstance(body, dict) or body.get("usage") is None:
        return None, []
    usage = body["usage"]
    if isinstance(usage, dict) and type(usage.get("input_tokens")) is int:
        return {"input_tokens": usage["input_tokens"]}, []
    return None, ["usage_input_tokens_invalid"]
