"""무엇: 출력 경로별 반올림 설정 · 입력: CLI 문자열 · 출력: 자리수/반단위 · 계약 §8-7 T-b/f."""


def parse(value):
    result = {"reference": None, "server": None}
    seen = set()
    for entry in value.split(",") if value else []:
        key, number = entry.split("=")
        if key not in result or key in seen or not number.isascii() or not number.isdecimal():
            raise ValueError("invalid rounding policy")
        digits = int(number)
        if not 0 <= digits <= 16:
            raise ValueError("rounding digits out of range")
        result[key] = digits
        seen.add(key)
    return result


def epsilon(digits):
    return None if digits is None else .5 * 10 ** -digits
