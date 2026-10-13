"""무엇: YAML 읽기·중복 거부 · 입력: 경로 · 출력: 객체/TaskSpec · 계약 §1-1·§8-1."""

from pathlib import Path

import yaml
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode

from jeveval.contract import taskspec
from jeveval.types import TaskSpec


class DuplicateKeyError(ConstructorError):
    """중첩 깊이와 무관한 YAML 중복 키 오류."""


class TaskSpecError(ValueError):
    """설정 파일의 전체 스키마 오류 목록."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("\n".join(errors))


class _UniqueLoader(yaml.SafeLoader):
    """전역 SafeLoader를 변경하지 않는 전용 로더."""

    def construct_mapping(self, node, deep=False):
        if not isinstance(node, MappingNode):
            return super().construct_mapping(node, deep=deep)
        self.flatten_mapping(node)
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                duplicate = key in result
            except TypeError as exc:
                raise ConstructorError(None, None, "unhashable key", key_node.start_mark) from exc
            if duplicate:
                raise DuplicateKeyError("mapping", node.start_mark,
                                        f"duplicate key: {key!r}", key_node.start_mark)
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def read_yaml(path: str | Path):
    """UTF-8 YAML을 SafeLoader 규칙으로 읽고 중복 키는 거부한다."""
    with Path(path).open(encoding="utf-8") as stream:
        return yaml.load(stream, Loader=_UniqueLoader)


def load_taskspec(path: str | Path) -> TaskSpec:
    """파일 읽기 후 순수 검사기로 위임한다. 실패하면 전체 오류를 예외에 담는다."""
    result = taskspec.validate_taskspec(read_yaml(path))
    if isinstance(result, list):
        raise TaskSpecError(result)
    return result
