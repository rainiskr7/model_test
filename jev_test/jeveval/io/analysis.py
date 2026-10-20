"""무엇: 질문 분석 등록 파일 읽기 · 입력: root · 출력: schema 객체/해시 · 계약 §7-4b."""

from jeveval.io.config import read_yaml
from jeveval.contract.analysis_declarations import normalize_declarations
from jeveval.io import variant_policy
from jeveval.io.hashes import sha256_file
from jeveval.io.paths import inside

MANIFEST = "configs/analysis/question_risk_v1.yaml"


def policy(root, name=MANIFEST):
    """기본 v1은 유지하고 명시된 동결 manifest만 등록 정책으로 읽는다."""
    path = inside(root, name)
    value = read_yaml(path)
    allowed = {"exploratory"} if name == MANIFEST else {"registered"}
    if value.get("schema") != "question_risk_policy/1" or value.get("status") not in allowed:
        raise ValueError("unsupported analysis registration")
    expected = dict(loss="answer_not_equal_gold", confidence="ParsedAnswer.confidence",
        validity="inherit_logical_request", unit="group_representative",
        missing="exclude_only_this_question", absent="exclude_and_count_separately",
        invalid="retain_labelled_present_in_denominator", taus=["0.01", "0.02", "0.05"],
        threshold="dev_risk_le_tau_over_two_max_coverage_tie_larger_t",
        kosgd="two_slots_one_bundle_min_confidence_order_independent_loss",
        korfin="aspect_k_position_conditional_on_presence", diagnostic="separate_table")
    claims = dict(scope="per_question_marginal", confidence_level=0.95, simultaneous=False,
                  family="all_reported_models_sets_variants_questions_taus",
                  note="질문을 골라 전체 결론으로 쓰지 않는다")
    if any(value.get(k) != v for k, v in expected.items()) or value.get("claims") != claims:
        raise ValueError("analysis policy differs from implemented rules")
    return value, sha256_file(path)


def declared_paths(root, fp):
    """동결 overlay만 읽으며 미선언 기본 셋은 현재 overlay를 찾지 않는다."""
    name = f"configs/sets/{fp.get('set')}.yaml"
    if name not in fp.get("files", {}):
        return {}
    path = inside(root, name)
    if sha256_file(path) != fp["files"][name]:
        raise ValueError("registered overlay changed")
    return normalize_declarations(read_yaml(path).get("analysis"))


def load_policy(root, kind, name):
    """선언 종류별 schema와 닫힌 정책을 확인한다."""
    if kind == "question_risk":
        return policy(root, name)
    if kind == "score_variants":
        return variant_policy.policy(root, name)
    raise ValueError("unknown analysis kind")


def declaration(root, fp, kind):
    """정책 경로와 바이트가 첫 fingerprint에 묶였는지 확인한다."""
    name = declared_paths(root, fp).get(kind)
    if name is None:
        return None, None, None
    value, digest = load_policy(root, kind, name)
    if digest != fp["files"].get(name):
        raise ValueError("manifest not frozen")
    return name, digest, value
