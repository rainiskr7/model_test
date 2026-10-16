"""무엇: T0 허용폭 규칙 읽기 · 입력: configs/t0/tolerance_v1.yaml 경로 · 출력: T0Policy(파일 해시 포함) · 계약 §8-7 T-d/e."""

from jeveval.contract.t0_policy import validate_t0_policy
from jeveval.io.config import read_yaml
from jeveval.io.hashes import sha256_file
from jeveval.types.t0_io import T0Policy


def read_t0_policy(path) -> T0Policy:
    """파일을 읽고 바이트 해시와 함께 순수 검사기로 위임한다."""
    result = validate_t0_policy(read_yaml(path), sha256_file(path))
    if isinstance(result, list):
        raise ValueError("; ".join(result))
    return result
