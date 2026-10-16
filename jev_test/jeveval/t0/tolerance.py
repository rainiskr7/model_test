"""무엇: 질문별 참조 변동 측정 · 입력: 고정 변형의 검증된 반복 결과 · 출력: T0Tolerance · 계약 §8-7 T-d/e."""

from jeveval.t0.distribution import nonnegative, vector, within
from jeveval.types.t0 import T0Tolerance, T0Variant
from jeveval.types.t0_io import T0Policy


def _unmeasured(questions, variants, repeats, reason):
    return {qid: T0Tolerance("unmeasured", "INCOMPLETE", None, None, list(variants), repeats, reason)
            for qid in questions}


def _check_samples(samples, variants, repeats):
    seen = set()
    for sample in samples:
        key = (sample.variant, sample.repeat)
        if sample.variant not in variants or type(sample.repeat) is not int or not 0 <= sample.repeat < repeats:
            raise ValueError("unexpected tolerance variant/repeat")
        if key in seen:
            raise ValueError("duplicate tolerance variant/repeat")
        seen.add(key)
    return seen == {(variant, repeat) for variant in variants for repeat in range(repeats)}


def measure(questions, samples: list[T0Variant], *, family, epsilon_r,
            target_sha256: dict[str, str], policy: T0Policy, batch_one_equal=False):
    """동일 대상 해시를 요구한다. 반복·변형·상한은 policy(configs/t0/tolerance_v1.yaml). Clef/v1은 배치 1 바이트 동일성이 선행한다."""
    if family not in policy.variants or not questions or target_sha256.keys() != questions.keys():
        raise ValueError("invalid tolerance family/targets")
    if epsilon_r is not None and not nonnegative(epsilon_r):
        raise ValueError("invalid rounding half-unit")
    variants, repeats = policy.variants[family], policy.repeats
    complete = _check_samples(samples, variants, repeats)
    if epsilon_r is None:
        return _unmeasured(questions, variants, repeats, "unknown_rounding")
    if family != "pplx_v1_1" and batch_one_equal is not True:
        return _unmeasured(questions, variants, repeats, "batch_one_not_verified")
    if not complete:
        return _unmeasured(questions, variants, repeats, "missing_variant")
    if any(s.target_sha256 != target_sha256 for s in samples):
        return _unmeasured(questions, variants, repeats, "target_mismatch")
    if any(s.response.reason or s.response.answers is None or
           s.response.answers.keys() != questions.keys() for s in samples):
        return _unmeasured(questions, variants, repeats, "reference_failure")
    result = {}
    for qid, question in questions.items():
        vectors = [vector(question, s.response.answers[qid]) for s in samples]
        variation = max(max(values) - min(values) for values in zip(*vectors, strict=True))
        unstable = not within(variation, policy.max_variation)
        result[qid] = T0Tolerance("measured" if variation else "measured_zero",
            "INCOMPLETE" if unstable else "PASS", variation,
            None if unstable else max(2 * variation, 2 * epsilon_r), list(variants), repeats,
            "unstable_reference" if unstable else None)
    return result
