"""무엇: YAML 읽기와 검사 위임 · 입력: 임시 합성 YAML · 출력: 검증 · 계약 §1-1."""

import pytest
import yaml

from jeveval.contract import taskspec
from jeveval.io.config import DuplicateKeyError, TaskSpecError, load_taskspec, read_yaml
from jeveval.types import TaskSpec


VALID_YAML = '''set: synthetic
variant: full
state:
  kind: plain_text
questions:
  - id: ready_1
    role: success
    type: noul
    instructions: 준비됐나요?
    criteria: {"true": "준비됐다.", "false": "아직이다."}
    label: ready
per_item_questions: null
group_key: source
'''


def write(tmp_path, source):
    path = tmp_path / "task.yaml"
    path.write_text(source, encoding="utf-8")
    return path


def test_utf8_to_taskspec(tmp_path):
    result = load_taskspec(write(tmp_path, VALID_YAML))
    assert isinstance(result, TaskSpec)
    assert result.questions[0].instructions == "준비됐나요?"
    assert result.questions[0].criteria == {"true": "준비됐다.", "false": "아직이다."}


@pytest.mark.parametrize("source", [
    "set: first\nset: second\n", "state: {kind: plain_text, kind: json_string}\n",
    "questions:\n  - criteria: {x: one, x: two}\n",
    "a:\n  b:\n    c: 1\n    c: 2\n", 'x: 1\n"x": 2\n',
    "a: &a {x: 1}\nb: {<<: *a, x: 2}\n",
    "a: &a {x: 1, x: 2}\nb: *a\n",
])
def test_reject_duplicates_at_any_depth(tmp_path, source):
    with pytest.raises(DuplicateKeyError, match="duplicate key"):
        read_yaml(write(tmp_path, source))


def test_yaml_alias_without_collision(tmp_path):
    result = read_yaml(write(tmp_path, "a: &a {x: 1}\nb: *a\n"))
    assert result == {"a": {"x": 1}, "b": {"x": 1}}


def test_contract_function_is_called(tmp_path, monkeypatch):
    seen = []
    def validate(data):
        seen.append(data)
        return ["synthetic rejection"]
    monkeypatch.setattr(taskspec, "validate_taskspec", validate)
    with pytest.raises(TaskSpecError) as error:
        load_taskspec(write(tmp_path, VALID_YAML))
    assert seen[0]["set"] == "synthetic"
    assert error.value.errors == ["synthetic rejection"]


def test_actual_schema_errors(tmp_path):
    with pytest.raises(TaskSpecError) as error:
        load_taskspec(write(tmp_path, VALID_YAML.replace("type: noul", "type: score")))
    assert any("score is out of scope" in e for e in error.value.errors)


@pytest.mark.parametrize("source", ["", "[]", "plain text"])
def test_nonobject_task(tmp_path, source):
    with pytest.raises(TaskSpecError):
        load_taskspec(write(tmp_path, source))


def test_loader_remains_safe(tmp_path):
    with pytest.raises(yaml.constructor.ConstructorError):
        read_yaml(write(tmp_path, "!!python/object/apply:builtins.print [unexpected]"))
    assert yaml.safe_load("enabled: true") == {"enabled": True}
