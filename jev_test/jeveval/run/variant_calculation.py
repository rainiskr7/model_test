"""무엇: 변형 계산 조립 · 입력: 복원 단계 · 출력: dev 정책/test 표 · 계약 §7-4d."""

from jeveval.score.isotonic import fit_isotonic
from jeveval.score.question_outcomes import observations
from jeveval.score.variant_scores import candidate_scores
from jeveval.score.variant_selection import select_variant_by_tau
from jeveval.score.variant_risk import apply_variant_policy


def development(stage):
    """dev만 보정기에 적합하며 정답 없는 성공 질문은 점수 투영에 남긴다."""
    units = observations(stage.finals, stage.items, "dev")
    keys = sorted({u.question_id for u in units if u.role == "success" and u.present})
    fits = {key: fit_isotonic((u.confidence, not u.wrong) for u in units
        if u.question_id == key and u.present and u.valid and u.gold is not None) for key in keys}
    candidates = candidate_scores(stage.outcomes, units, fits)
    return dict(calibrators=fits, by_tau=select_variant_by_tau(candidates))


def trial(stage, policy):
    """test 라벨은 손실에만 쓰며 보정기나 선택에는 전달하지 않는다."""
    units = observations(stage.finals, stage.items, "test")
    candidates = candidate_scores(stage.outcomes, units, policy["calibrators"])
    return apply_variant_policy(candidates, policy["by_tau"])
