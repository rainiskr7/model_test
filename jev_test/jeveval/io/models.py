"""무엇: 모델 YAML 읽기 · 입력: 경로 · 출력: ModelConfig/오류 목록 · 계약 §8-6 G·J."""

from pathlib import Path

from jeveval.contract.model_config import validate_model_config
from jeveval.io.config import read_yaml
from jeveval.types import ModelConfig


class ModelConfigError(ValueError):
    """모델 설정의 경로별 오류 목록."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("\n".join(errors))


def load_model_config(path) -> ModelConfig:
    """중복 키를 거부하는 공통 YAML 로더 뒤에 순수 검사를 적용한다."""
    path = Path(path)
    result = validate_model_config(read_yaml(path), path.stem)
    if isinstance(result, list):
        raise ModelConfigError(result)
    return result
