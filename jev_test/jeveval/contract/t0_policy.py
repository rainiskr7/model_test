"""무엇: T0 허용폭 규칙 스키마 검사 · 입력: tolerance yaml 객체·파일 해시 · 출력: T0Policy 또는 오류 목록 · 계약 §8-7 T-d/e."""

import math
import re

from jeveval.types.t0_io import T0Policy


def validate_t0_policy(data, sha256: str) -> T0Policy | list[str]:
    """닫힌 키·양의 정수 반복·비음수 유한 상한·계열별 고유 변형 목록(pplx_v1_1 필수)만 받는다."""
    if (not isinstance(data, dict) or set(data) != {"schema", "repeats", "max_variation", "variants"}
            or data["schema"] != "t0_tolerance_policy/1"):
        return ["t0 policy requires schema t0_tolerance_policy/1 with repeats, max_variation, variants"]
    errors = []
    repeats, bound, variants = data["repeats"], data["max_variation"], data["variants"]
    if type(repeats) is not int or repeats < 1:
        errors.append("repeats must be a positive integer")
    if type(bound) not in (int, float) or not math.isfinite(bound) or bound < 0:
        errors.append("max_variation must be a nonnegative finite number")
    if not isinstance(variants, dict) or not variants or "pplx_v1_1" not in variants:
        errors.append("variants must map model families (including pplx_v1_1) to variant lists")
    else:
        for family, names in variants.items():
            if (type(family) is not str or not isinstance(names, list) or not names
                    or any(type(n) is not str or not n for n in names) or len(set(names)) != len(names)):
                errors.append(f"variants[{family!r}] must be a non-empty list of unique names")
    if type(sha256) is not str or not re.fullmatch(r"[0-9a-f]{64}", sha256):
        errors.append("policy sha256 must be a hex digest")
    return errors or T0Policy(repeats, float(bound), {k: list(v) for k, v in variants.items()}, sha256)
