"""무엇: T0 용 길이 측정·경계 요청 생성 · 입력: 모델 인코더(Measurer)·T0Request·목표 길이 · 출력: 총 길이·경계 T0Request · 계약 §8-7 T-c/T-g."""

from copy import deepcopy

from jeveval.t0.request import build_request
from jeveval.types import CallPlan, Rendered, Request
from jeveval.types.t0 import T0Request

FILLERS = (" a", " b", "a", ".")
MAX_DOUBLINGS = 24


def _plan(request: T0Request) -> CallPlan:
    """본시험 인코더(Measurer)가 받는 CallPlan 모양으로 T0 요청을 감싼다. 전송용이 아니다."""
    body = request.body
    return CallPlan("t0", "t0", "systemone", list(body["questions"]),
                    {qid: q["type"] for qid, q in body["questions"].items()}, request.envelope_bytes,
                    request.request_sha256, Request(body["model"], body["state"], deepcopy(body["questions"])),
                    None, Rendered(body["state"], request.target_end_char), [])


def measure_with(measurer):
    """t0 inputs 의 measurer(request) -> 총 길이(래퍼 포함) 어댑터."""
    def length(request: T0Request) -> int:
        return measurer.measure(_plan(request)).length_tokens
    return length


def _with_state(base: T0Request, state: str) -> T0Request:
    body = base.body
    return build_request(body["model"], state, {"kind": "plain_text"}, deepcopy(body["questions"]),
                         images=body.get("images"))


def _grow(base, state, filler, target, length):
    """채움 개수를 두 배씩 늘려 target 이상을 찾고 이분 탐색으로 가장 작은 개수를 고른다. 정확히 맞을 때만 요청을 준다."""
    low, high = 0, 1
    while length(_with_state(base, state + filler * high)) < target:
        low, high = high, high * 2
        if high > 1 << MAX_DOUBLINGS:
            return None
    while high - low > 1:
        mid = (low + high) // 2
        if length(_with_state(base, state + filler * mid)) < target:
            low = mid
        else:
            high = mid
    request = _with_state(base, state + filler * high)
    return request if length(request) == target else None


def boundary_builder_with(measurer):
    """t0 inputs 의 boundary_builder(base, target) -> (요청, [총 길이]). state 꼬리에만 채움을 붙이고 질문·모델은 그대로 둔다."""
    length = measure_with(measurer)

    def build(base: T0Request, target: int):
        if type(target) is not int or target <= 0:
            raise ValueError("target length must be a positive integer")
        state = base.body["state"]
        if not isinstance(state, str):
            raise ValueError("boundary base state must be a string")
        current = length(base)
        if current > target:
            raise ValueError("base request already exceeds the target length")
        if current == target:
            return base, [target]
        for filler in FILLERS:
            request = _grow(base, state, filler, target, length)
            if request is not None:
                return request, [target]
        raise ValueError("boundary builder could not hit the target length")
    return build
