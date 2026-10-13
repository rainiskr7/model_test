"""무엇: 순수 길이 판정 · 입력: LengthInfo·문자 offsets · 출력: 잘림/구간/토큰 끝 · 계약 §4-3."""

from typing import Literal, Protocol

from jeveval.types import CallPlan, LengthInfo


class Measurer(Protocol):
    """P0의 서버 인코더 측정 구현을 주입하는 경계."""

    def measure(self, plan: CallPlan) -> LengthInfo:
        """전송할 호출의 래퍼 포함 길이와 state 대상 끝을 잰다."""
        ...


def classify(info: LengthInfo) -> Literal["not_truncated", "target_cut", "tail_cut"]:
    """상한과 같은 길이는 잘림이 아니며 초과 때 대상 끝 위치로 구분한다."""
    if info.length_tokens <= info.limit:
        return "not_truncated"
    return "target_cut" if info.target_end > info.limit - info.fixed_tokens else "tail_cut"


def token_end(offsets: list[tuple[int, int]], char_end: int) -> int:
    """정렬·비겹침 offsets에서 대상 마지막 문자를 덮는 토큰의 다음 번호를 준다."""
    if type(char_end) is not int or char_end < 0:
        raise ValueError("char_end must be a nonnegative integer")
    previous, found = 0, None
    for index, pair in enumerate(offsets):
        if len(pair) != 2:
            raise ValueError("expected (start, end) offset")
        start, end = pair
        if (type(start) is not int or type(end) is not int
                or start < previous or end < start):
            raise ValueError("offsets must be nonnegative, sorted and nonoverlapping")
        if start <= char_end - 1 < end:
            found = index + 1
        previous = end
    if char_end == 0:
        return 0
    if found is None:
        raise ValueError("target character is not covered by offsets")
    return found


def length_bucket(n: int) -> Literal["le_4096", "le_8192", "le_16384", "gt_16384"]:
    """논리 요청 호출들의 최대 입력 길이에 적용할 구간 이름을 반환한다."""
    if type(n) is not int or n < 0:
        raise ValueError("length must be a nonnegative integer")
    for limit in (4096, 8192, 16384):
        if n <= limit:
            return f"le_{limit}"
    return "gt_16384"
