"""무엇: 문맥 타입 불변성 · 입력: 기존 합성 표본 · 출력: frozen/replace 문맥 · 계약 §8-1·§8-6."""

from dataclasses import FrozenInstanceError, replace

import pytest

from jeveval.types import B1Config, FinalRecord, ModelConfig, RunContext, SplitPlan, StageData, TaskSpec
from tests.types import samples


@pytest.fixture
def ctx(tmp_path):
    values = {type(value): value for value in samples.records()}
    cfg = ModelConfig(id="synthetic", kind="systemone", served_name="fake", base_url=None,
        auth_env=None, question_scoring="separate", limit={"tokens": 100, "overflow": "reject"},
        input_limit_response=None, encoder={}, tokenizer={}, concurrency=1, b1=None,
        serving={}, repo={}, t0={}, notes="")
    return RunContext(tmp_path, tmp_path / "model.yaml", tmp_path / "task.yaml", cfg,
                      values[TaskSpec], values[SplitPlan], values[B1Config])


@pytest.mark.parametrize("field,value", [("directory", "changed"), ("fingerprint", {})])
def test_run_context_is_frozen(ctx, field, value):
    with pytest.raises(FrozenInstanceError):
        setattr(ctx, field, value)


def test_replace_fills_run_context_without_mutating_original(ctx):
    directory = ctx.root / "run"
    fingerprint = {"schema": "fingerprint/1", "run_id": "r1"}
    restored = replace(ctx, directory=directory, fingerprint=fingerprint)
    assert isinstance(restored, RunContext) and restored is not ctx
    assert restored.directory == directory and restored.fingerprint == fingerprint
    assert ctx.directory is None and ctx.fingerprint is None
    assert replace(restored, directory=None, fingerprint=None) == ctx


@pytest.mark.parametrize("field", ["finals", "items", "outcomes", "warnings"])
def test_stage_data_is_frozen(field):
    final = next(value for value in samples.records() if isinstance(value, FinalRecord))
    item = samples.item()
    data = StageData([final], {f"{item.set}:{item.group_id}:{item.item_id}": item},
                     [samples.outcome()], [])
    with pytest.raises(FrozenInstanceError):
        setattr(data, field, getattr(data, field))
