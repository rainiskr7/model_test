"""무엇: dev 후보 선택 · 입력: 후보별 dev 요청 · 출력: τ별 동결 선택 · 계약 §7-4d."""

from jeveval.score.threshold import TAUS, select
from jeveval.score.variant_scores import CANDIDATES


def select_variant_by_tau(candidates):
    """수락 수 최대, 동점은 닫힌 후보 순서이며 test는 받지 않는다."""
    if set(candidates) != set(CANDIDATES) or any(r.stage != "dev" for rows in candidates.values() for r in rows):
        raise ValueError("expected dev candidates")
    result = {}
    for tau in TAUS:
        thresholds = {name: select(candidates[name], tau) for name in CANDIDATES}
        name = max(CANDIDATES, key=lambda n: thresholds[n].n_accepted or 0)
        result[tau] = dict(candidate=name, threshold=thresholds[name].to_dict())
    return result
