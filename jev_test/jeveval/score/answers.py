"""무엇: 응답을 답·확신으로 변환 · 입력: 검증 답/B1 로그확률 · 출력: AnswerParse · 계약 §3-2."""

from copy import deepcopy
import math

from jeveval.types import AnswerParse, ParsedAnswer


def _noul(p):
    return ParsedAnswer("noul", "true" if p >= .5 else "false",
                        {"true": p, "false": 1 - p}, max(p, 1 - p))


def _check_type(qtype):
    if qtype == "score":
        raise NotImplementedError("score is out of scope")
    if qtype not in ("noul", "choice"):
        raise ValueError("expected noul or choice")


def parse_systemone(answer: dict, qtype: str) -> AnswerParse:
    """검증된 확률·확신을 재정규화하거나 반올림하지 않는다."""
    _check_type(qtype)
    warnings = []
    if qtype == "noul":
        parsed = _noul(answer["noul"])
    else:
        probs = deepcopy(answer["probabilities"])
        parsed = ParsedAnswer(qtype, answer["choice"], probs, answer["confidence"])
        if probs[parsed.answer] < max(probs.values()) - 1e-9:
            warnings.append("choice_not_argmax")
    return AnswerParse(parsed, None, warnings, None)


def _label_logs(rows, labels):
    logs, warnings = {}, []
    for row in rows:
        label = row["token"].strip()
        if label not in labels:
            warning = "b1_extra_token"
        else:
            value = row["logprob"]
            warning = "b1_duplicate_label" if label in logs else None
            logs[label] = max(logs[label], value) if label in logs else value
        if warning is not None and warning not in warnings:
            warnings.append(warning)
    return logs, warnings


def parse_b1(top_logprobs: list[dict], label_order: list[str],
             label_map: dict[str, str], qtype: str) -> AnswerParse:
    """라벨 후보만 softmax하고 choice 동률은 응답 토큰 순서가 아닌 라벨 순서로 푼다."""
    _check_type(qtype)
    logs, warnings = _label_logs(top_logprobs, label_order)
    if any(label not in logs or not math.isfinite(logs[label]) or logs[label] <= -9999
           for label in label_order):
        return AnswerParse(None, "b1_missing_label", warnings, None)
    maximum = max(logs[label] for label in label_order)
    weights = {label: math.exp(logs[label] - maximum) for label in label_order}
    total = math.fsum(weights.values())
    label_probs = {label: weight / total for label, weight in weights.items()}
    if qtype == "noul":
        true_label = next(label for label in label_order if label_map[label] == "true")
        parsed = _noul(label_probs[true_label])
    else:
        winner = max(label_order, key=label_probs.get)
        probs = {label_map[label]: label_probs[label] for label in label_order}
        parsed = ParsedAnswer(qtype, label_map[winner], probs, label_probs[winner])
    return AnswerParse(parsed, None, warnings, label_probs)
