"""무엇: 정책 YAML 경계 · 입력: 동결 정책/잘못된 YAML · 출력: RetryPolicy/결합 오류 · 계약 §4-2·§8-1."""

from pathlib import Path

import pytest

from jeveval.io.config import DuplicateKeyError
from jeveval.io.policy import read_retry_policy
from jeveval.types import RetryPolicy


def test_repository_policy_matches_declared_retry_rules():
    path = Path(__file__).resolve().parents[2] / "configs/policy.yaml"
    assert read_retry_policy(path) == RetryPolicy(5, [503, 529], [1, 2, 4, 8])


@pytest.mark.parametrize("text", ["retry: {}\nretry: {}\n",
    "retry:\n  max_attempts: 5\n  max_attempts: 4\n  http_statuses: [503]\n  backoff_seconds: [1, 2, 4]\n"])
def test_duplicate_yaml_keys_rejected(tmp_path, text):
    path = tmp_path / "policy.yaml"
    path.write_text(text)
    with pytest.raises(DuplicateKeyError, match="duplicate key"):
        read_retry_policy(path)


def test_policy_validation_messages_are_joined(tmp_path):
    path = tmp_path / "policy.yaml"
    path.write_text("retry:\n  max_attempts: 0\n  http_statuses: [true]\n  backoff_seconds: [.nan]\n")
    with pytest.raises(ValueError) as error:
        read_retry_policy(path)
    assert str(error.value) == (
        "max_attempts must be a positive integer; "
        "http_statuses must be unique HTTP status integers; "
        "backoff_seconds must list one nonnegative wait per non-final attempt")
