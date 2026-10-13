"""무엇: 순수 결과 변환 · 입력: 계획·시도·길이·설정 · 출력: 호출/논리 기록 · 계약 §3–5·§8-6."""

from copy import deepcopy
import re

from jeveval.contract.b1_response import read_b1_response, storable_top_logprobs
from jeveval.contract.response import read_usage, validate_response
from jeveval.score.answers import parse_b1, parse_systemone
from jeveval.types import AttemptRecord, CallPlan, CallRecord, FinalRecord, LengthInfo, ModelConfig
from .length import classify
from .policy import MAX_ATTEMPTS


def _check_attempts(plan, attempts, max_attempts):
    """복구할 기록의 누적 예산·연속성·현재 계획 연결·완료 여부를 검사한다."""
    if type(max_attempts) is not int or max_attempts < 1 or not 1 <= len(attempts) <= max_attempts:
        raise ValueError("expected 1..max_attempts recorded attempts")
    for index, attempt in enumerate(attempts, 1):
        if (attempt.attempt != index or attempt.call_id != plan.call_id
                or attempt.logical_id != plan.logical_id
                or attempt.request_sha256 != plan.request_sha256):
            raise ValueError("attempt does not match sequence or current plan")
        if attempt.terminal and index != len(attempts):
            raise ValueError("attempt after terminal")
    if not attempts[-1].terminal and len(attempts) < max_attempts:
        raise ValueError("call is not complete")


def _answers(plan, raw, b1_response):
    """HTTP 200의 답을 전부 검증하며 실패에도 이미 모은 경고와 B1 원분포를 남긴다."""
    if plan.kind == "systemone":
        validated = validate_response(raw, plan.request)
        warnings = list(validated.warnings)
        if validated.reason:
            return validated.reason, warnings, None, None
        answers = {}
        for qid in plan.question_ids:
            parsed = parse_systemone(validated.answers[qid], plan.question_types[qid])
            answers[qid] = parsed.parsed
            warnings.extend(parsed.warnings)
        return None, warnings, answers, None
    if b1_response.reason:
        return b1_response.reason, [], None, None
    call, qid = plan.b1_call, plan.question_ids[0]
    parsed = parse_b1(b1_response.top_logprobs, call.label_order,
                      call.label_map, plan.question_types[qid])
    stored = storable_top_logprobs(b1_response.top_logprobs)
    return (parsed.reason, parsed.warnings,
            None if parsed.reason else {qid: parsed.parsed}, stored)


def _response_record(plan, attempt, length, cfg):
    """사용량을 독립 추출한 뒤 전송 오류·HTTP·답·길이 순서로 결과를 결합한다."""
    raw, b1_response = attempt.response_raw, None
    if plan.kind == "b1":
        b1_response = read_b1_response(raw)
        usage, usage_warnings = b1_response.usage, b1_response.warnings
    else:
        usage, usage_warnings = read_usage(raw)
    status, reason, warnings, answers, top = "error", None, [], None, None
    if attempt.transport_error is not None:
        reason = "timeout" if attempt.transport_error == "timeout" else "transport"
    elif attempt.http_status == 200:
        reason, warnings, answers, top = _answers(plan, raw, b1_response)
        if plan.kind == "b1":
            warnings = usage_warnings + warnings
        if reason is None:
            cut = classify(length)
            status, reason = ("ok", None) if cut == "not_truncated" else ("truncated", cut)
            if (cut == "not_truncated" and usage is not None
                    and usage["input_tokens"] != length.length_tokens):
                warnings.append("length_mismatch")
    elif (cfg.input_limit_response
          and attempt.http_status == cfg.input_limit_response["status"]
          and isinstance(raw, str)
          and re.search(cfg.input_limit_response["body_regex"], raw)):
        status, reason = "rejected", "input_limit"
    elif attempt.http_status == 422:
        reason = "http_422_other"
    else:
        reason = f"http_{attempt.http_status}"
    return status, reason, list(dict.fromkeys(warnings + usage_warnings)), usage, answers, top


def call_record(plan: CallPlan, attempts: list[AttemptRecord], length: LengthInfo | None,
                cfg: ModelConfig, max_attempts: int = MAX_ATTEMPTS) -> CallRecord:
    """로컬 오류 외에는 길이와 완료 기록이 필요하며 예산 소진도 terminal처럼 복구한다."""
    label_map = deepcopy(plan.b1_call.label_map) if plan.kind == "b1" and plan.b1_call else None
    if plan.local_errors:
        return CallRecord(plan.call_id, 0, "error", "request_contract", [],
                          plan.request_sha256, None, None, None, label_map)
    if length is None:
        raise ValueError("length is required for every sent call")
    _check_attempts(plan, attempts, max_attempts)
    status, reason, warnings, usage, answers, top = _response_record(plan, attempts[-1], length, cfg)
    return CallRecord(plan.call_id, len(attempts), status, reason, warnings,
                      plan.request_sha256, length, usage, answers, label_map, top)


def final_record(logical_id: str, plans: list[CallPlan], calls: list[CallRecord]) -> FinalRecord:
    """계획 순서로 최악 상태의 첫 사유와 경고를 고르고 일부 성공 답도 보존한다."""
    if not plans or [p.call_id for p in plans] != [c.call_id for c in calls]:
        raise ValueError("call order must match nonempty plans")
    if any(p.logical_id != logical_id for p in plans):
        raise ValueError("plans must belong to logical_id")
    rank = {"ok": 0, "truncated": 1, "rejected": 2, "error": 3}
    worst = max(calls, key=lambda call: rank[call.status])
    warnings = list(dict.fromkeys(w for call in calls for w in call.warnings))
    over = any(call.status == "truncated" and call.answers_parsed is not None for call in calls)
    return FinalRecord(logical_id, worst.status, None if worst.status == "ok" else worst.reason,
                       over, warnings, deepcopy(calls), None)
