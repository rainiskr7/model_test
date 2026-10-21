"""무엇: T0 단계 진입 시험 · 입력: 합성 bundle/seam · 출력: 단계 인자 격리 · 계약 §8-7."""

import pytest

from jeveval.run import cmd_t0
from tests.run.file_support import output_files
from tests.t0_io.support import inputs, setup, stage


def test_unknown_stage_is_rejected_without_writes(setup):
    ctx = setup()
    inputs(ctx)
    before = output_files(ctx.directory)
    with pytest.raises(ValueError, match="^unknown T0 stage$"):
        stage(ctx, "unknown")
    assert output_files(ctx.directory) == before


def test_inputs_directory_follows_model_and_run_id(setup):
    ctx = setup()
    result = inputs(ctx)
    assert result["ok"] is True
    assert ctx.directory == ctx.root / "results/_t0/clef/r1"
    assert set(output_files(ctx.directory)) == {"inputs.jsonl", "fingerprint.json"}


@pytest.mark.parametrize("run_id", ["../escape", "nested/id", "", "."])
def test_inputs_reject_invalid_run_id_before_writes(setup, run_id):
    ctx = setup()
    before = output_files(ctx.root)
    with pytest.raises(ValueError):
        cmd_t0.run(root=ctx.root, stage="inputs", model="clef.yaml", run_id=run_id,
                   fixture="fixture.json", sources=ctx.sources)
    assert output_files(ctx.root) == before


def test_reference_requires_checkpoint_without_writes(setup):
    ctx = setup()
    inputs(ctx)
    before = output_files(ctx.directory)
    with pytest.raises(ValueError, match="^local checkpoint required$"):
        stage(ctx, "reference", runtime=ctx.runtime)
    assert output_files(ctx.directory) == before


@pytest.mark.parametrize("stage_name,foreign", [
    ("inputs", "runtime"), ("reference", "post"), ("server", "sources"),
    ("tolerance", "runtime"), ("judge", "measurer")])
def test_stage_entrypoints_reject_foreign_seams(stage_name, foreign):
    import inspect
    handler = cmd_t0.stage_handler(stage_name)
    assert foreign not in inspect.signature(handler).parameters
    with pytest.raises(TypeError):
        handler(**{foreign: object()})
