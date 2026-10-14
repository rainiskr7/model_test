"""무엇: 본시험 T0 기록 읽기 경계 · 입력: 저장소/모델 YAML 경로 · 출력: 검증/거부 · 계약 §8-7 T-i."""

from jeveval.io.models import load_model_config
from jeveval.io.run_inputs import inside
from jeveval.t0.gate import check_record


def verify_for_run(root, model_path):
    """CLI base_url 재정의 전 YAML 원본을 검사하고 쓰기·모델 로딩 전에 실패한다."""
    cfg = load_model_config(model_path)
    if cfg.t0["status"] != "passed":
        return
    try:
        path = inside(root, cfg.t0["record"]["path"])
        payload = path.read_bytes()
    except (OSError, ValueError):
        raise ValueError("T0 record unavailable") from None
    errors = check_record(cfg.to_dict(), payload)
    if errors:
        raise ValueError("T0 gate failed: " + ", ".join(errors))
