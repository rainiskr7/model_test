"""무엇: 확신 후보 투영 · 입력: 요청/질문 단위/보정기 · 출력: 후보별 요청 점수 · 계약 §7-4d."""

from collections import defaultdict
from dataclasses import replace
from math import prod

from jeveval.score.isotonic import apply_isotonic

CANDIDATES = ("min", "product", "iso_min", "iso_product")


def candidate_scores(requests, units, calibrators):
    """손실·분모·유효성은 원 요청을 유지하고 성공 단위의 점수만 바꾼다."""
    by_id = defaultdict(list)
    for unit in units:
        if unit.role == "success" and unit.present:
            by_id[unit.logical_id].append(unit)
    result = {name: [] for name in CANDIDATES}
    for row in requests:
        values = dict.fromkeys(CANDIDATES)
        if row.valid:
            selected = sorted(by_id[row.logical_id], key=lambda u: u.question_id)
            if not selected or len({u.question_id for u in selected}) != len(selected):
                raise ValueError("invalid success units")
            raw = [u.confidence for u in selected]
            calibrated = [apply_isotonic(calibrators.get(u.question_id, dict(x=[], y=[])), u.confidence)
                          for u in selected]
            if min(raw) != row.s:
                raise ValueError("min candidate differs from primary score")
            values = dict(zip(CANDIDATES, (row.s, prod(raw), min(calibrated), prod(calibrated))))
        for name in CANDIDATES:
            result[name].append(replace(row, s=values[name]))
    return result
