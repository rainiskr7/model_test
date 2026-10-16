"""무엇: 재시도 정책 읽기 · 입력: configs/policy.yaml 경로 · 출력: RetryPolicy · 계약 §4-2·§8-1."""

from jeveval.contract.policy import validate_retry_policy
from jeveval.io.config import read_yaml
from jeveval.types import RetryPolicy


def read_retry_policy(path) -> RetryPolicy:
    """파일을 읽고 순수 검사기로 위임한다. 오류는 전부 모아 ValueError 로 낸다."""
    result = validate_retry_policy(read_yaml(path))
    if isinstance(result, list):
        raise ValueError("; ".join(result))
    return result
