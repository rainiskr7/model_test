"""벤치마크 결과 표준 schema + sanity check — 참조 ../../../model_test/shared/multimodal/benches/_schema.py 대응.

참조는 Pydantic 을 쓰지만 이 하니스는 추가 의존성을 피하려 순수 stdlib 로 동일 키 구조 +
detect_and_validate(키 기반 검사)를 제공한다. 결과 JSON 의 '모양'은 참조와 호환된다.

표준 필드(참조 §5):
  공통        : benchmark, model, total
  accuracy형  : + correct, accuracy, by_category
  점수형(신규): + metric, score, by_subset
    └ 임베딩/리랭커는 accuracy 가 아니라 spearman/ndcg/mrr 등 연속 점수라 별도 변형을 둔다.

sanity check(run_all 류)가 total==0 / 비정상 점수를 즉시 잡도록 표준화.
"""

from __future__ import annotations

from typing import Optional


_NUM = (int, float)


def _require(d: dict, keys: tuple[str, ...], file_path: str) -> Optional[str]:
    missing = [k for k in keys if k not in d]
    if missing:
        return f"{file_path}: 필수 필드 누락 {missing}"
    return None


def detect_and_validate(d: dict, file_path: str = "<json>") -> tuple[str, Optional[str]]:
    """결과 JSON 의 종류 자동 감지 + 검증.

    Returns (kind, error_msg):
      kind     : 'score' | 'accuracy' | 'latency' | 'unknown'
      error_msg: None 이면 OK, 문자열이면 경고/오류
    """
    if not isinstance(d, dict):
        return "unknown", f"{file_path}: dict 가 아님({type(d).__name__})"

    # latency: conditions 리스트
    if "conditions" in d:
        err = _require(d, ("benchmark", "model", "conditions"), file_path)
        if err:
            return "latency", err
        if not isinstance(d["conditions"], list) or not d["conditions"]:
            return "latency", f"{file_path}: conditions 가 비어있거나 리스트가 아님"
        return "latency", None

    # 점수형(신규): metric+score
    if "metric" in d and "score" in d:
        err = _require(d, ("benchmark", "model", "total", "metric", "score"), file_path)
        if err:
            return "score", err
        if not isinstance(d["total"], int) or isinstance(d["total"], bool):
            return "score", f"{file_path}: total 이 int 가 아님"
        if not isinstance(d["score"], _NUM) or isinstance(d["score"], bool):
            return "score", f"{file_path}: score 가 숫자가 아님"
        if d["total"] == 0:
            return "score", f"{file_path}: score total=0 (데이터 로드 실패 의심)"
        return "score", None

    # accuracy형
    if "accuracy" in d and "correct" in d:
        err = _require(d, ("benchmark", "model", "total", "correct", "accuracy"), file_path)
        if err:
            return "accuracy", err
        if not isinstance(d["total"], int) or isinstance(d["total"], bool):
            return "accuracy", f"{file_path}: total 이 int 가 아님"
        acc = d["accuracy"]
        if not isinstance(acc, _NUM) or isinstance(acc, bool):
            return "accuracy", f"{file_path}: accuracy 가 숫자가 아님"
        if d["total"] == 0:
            return "accuracy", f"{file_path}: accuracy total=0"
        if not (0.0 <= acc <= 1.0):
            return "accuracy", f"{file_path}: accuracy={acc} 범위 밖(0~1)"
        if acc < 0.05:
            return "accuracy", f"{file_path}: accuracy={acc:.3f} 매우 낮음(broken template 의심)"
        return "accuracy", None

    return "unknown", None


def make_score_summary(
    *,
    benchmark: str,
    model: str,
    total: int,
    metric: str,
    score: float,
    by_subset: Optional[dict] = None,
    run_config: Optional[dict] = None,
    extra: Optional[dict] = None,
) -> dict:
    """점수형 표준 summary dict 생성(임베딩 STS/Retrieval/Clustering 등)."""
    out = {
        "benchmark": benchmark,
        "model": model,
        "total": total,
        "metric": metric,
        "score": score,
    }
    if by_subset is not None:
        out["by_subset"] = by_subset
    if extra:
        out.update(extra)
    if run_config is not None:
        out["run_config"] = run_config
    return out
