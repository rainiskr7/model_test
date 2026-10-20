"""무엇: 확신 변형 정책 읽기 · 입력: 정책 경로 · 출력: 검증된 정책/해시 · 계약 §7-4d."""

import yaml

from jeveval.io.config import read_yaml
from jeveval.io.hashes import sha256_file
from jeveval.io.paths import inside

MANIFEST = "configs/analysis/score_variants_v1.yaml"
EXPECTED = dict(schema="score_variants_policy/1", status="registered",
    candidates=["min", "product", "iso_min", "iso_product"],
    unit="success_question_slots_min_bundle", missing="include_in_score",
    fit="dev_valid_labelled_per_unit", isotonic="pav_nondecreasing_ties_mean",
    fallback="identity_empty_single_class_or_unseen", apply="step_floor_clip_endpoints",
    select="max_dev_accepted_candidate_order", no_threshold="min",
    taus=["0.01", "0.02", "0.05"],
    claims=dict(scope="per_cell_marginal", confidence_level=0.95, simultaneous=False,
                score_is_probability=False, dev_is_generalization=False))


def policy(root, name=MANIFEST):
    """닫힌 정책의 값과 키가 구현 규칙에 정확히 맞아야 한다."""
    path = inside(root, name)
    try:
        value = read_yaml(path)
    except yaml.YAMLError:
        raise ValueError("invalid variant policy YAML") from None
    if value != EXPECTED:
        raise ValueError("variant policy differs from implemented rules")
    return value, sha256_file(path)
