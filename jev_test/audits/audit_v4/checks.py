"""직렬화된 감사 입력에 대한 순수 R4/R7/바이트 검사와 길이 집계."""

import json
import math

from audits.audit_v4.independent.requests import wire


def r4(actual, expected):
    """JSON 문자열을 다시 읽고 순서·원문·키·전체 요청 ID를 비교한다."""
    if set(actual) != set(expected) or not actual:
        return "FAIL"
    for lid, record in actual.items():
        try:
            state = json.loads(record["state"])
            source = json.loads(expected[lid]["state"])
            dialogue = state["dialogue"]
            if (set(state) != {"dialogue", "catalog"} or not dialogue or dialogue[-1]["speaker"] != "USER" or
                    any(set(t) != {"speaker", "utterance"} for t in dialogue) or
                    wire(state) != wire(source) or wire(record["questions"]) != wire(expected[lid]["questions"])):
                return "FAIL"
        except (ValueError, KeyError, TypeError):
            return "FAIL"
    return "PASS"


def r7(actual, expected, requests=None, expected_requests=None):
    if requests is not None and (set(requests) != set(expected_requests) or any(
            wire(requests[k]["questions"]) != wire(expected_requests[k]["questions"]) for k in requests)):
        return "FAIL"
    if not actual or set(actual) != set(expected):
        return "FAIL"
    for lid, qs in actual.items():
        if set(qs) != set(expected[lid]):
            return "FAIL"
        for qid, q in qs.items():
            target = expected[lid][qid]
            if q != target or type(q["gold"]) is not str or type(q["gold"]) is not type(target["gold"]):
                return "FAIL"
    return "PASS"


def hashes(body, expected, captured, actual_map, expected_map):
    return "PASS" if body == expected == captured and actual_map == expected_map else "FAIL"


def lengths(values, limit):
    if not values:
        return dict(status="INCOMPLETE", denominator=0)
    ordered = sorted(values)
    def percentile(f):
        index = (len(ordered)-1)*f
        low, high = math.floor(index), math.ceil(index)
        return ordered[low] + (ordered[high]-ordered[low])*(index-low)
    return dict(status="FAIL" if max(values) > 8192 else "PASS", denominator=len(values),
                over_8192=sum(v > 8192 for v in values), over_model_limit=sum(v > limit for v in values),
                model_limit=limit, p50=percentile(.5), p95=percentile(.95), max=max(values))


def combine(values):
    return "FAIL" if "FAIL" in values else "INCOMPLETE" if "INCOMPLETE" in values or not values else "PASS"
