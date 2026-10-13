"""무엇: B1 응답 읽기 · 입력: 응답 원문/로그확률 · 출력: B1Response/저장용 사본 · 계약 §5-5b."""

from copy import deepcopy
import json
import math

from jeveval.types import B1Response


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _usage(body):
    usage = body.get("usage")
    if usage is None:
        return None, []
    if isinstance(usage, dict) and type(usage.get("prompt_tokens")) is int:
        return {"input_tokens": usage["prompt_tokens"]}, []
    return None, ["usage_input_tokens_invalid"]


def _top_logprobs(body):
    rows = body["choices"][0]["logprobs"]["content"][0]["top_logprobs"]
    if not isinstance(rows, list):
        raise ValueError("expected top_logprobs list")
    result = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("token"), str):
            raise ValueError("expected token string")
        value = row.get("logprob")
        if type(value) not in (int, float):
            raise ValueError("expected numeric logprob")
        value = float(value)
        if math.isnan(value) or value > 0:
            raise ValueError("expected nonpositive logprob")
        result.append(dict(row, logprob=value))
    return result


def read_b1_response(raw: str | bytes) -> B1Response:
    """중복 키·형식을 검사하되 답 구조가 틀려도 usage와 경고를 남긴다."""
    try:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        body = json.loads(raw, object_pairs_hook=_unique_object)
        if not isinstance(body, dict):
            raise ValueError("expected object")
    except (ValueError, TypeError):
        return B1Response("bad_body", [], None, None)
    usage, warnings = _usage(body)
    try:
        rows = _top_logprobs(body)
    except (KeyError, IndexError, TypeError, ValueError, OverflowError):
        return B1Response("bad_body", warnings, None, usage)
    return B1Response(None, warnings, rows, usage)


def storable_top_logprobs(top_logprobs: list[dict]) -> list[dict]:
    """메모리의 float -inf를 바꾸지 않고 기록용 사본에만 문자열로 둔다."""
    rows = deepcopy(top_logprobs)
    for row in rows:
        if row.get("logprob") == float("-inf"):
            row["logprob"] = "-inf"
    return rows
