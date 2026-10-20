"""동결 입력 이후 정책 변경은 파생 증거를 쓰기 전에 거부한다."""

import pytest

from jeveval.io.config import read_yaml
from tests.run.file_support import output_files, put_yaml
from .support import fake_post, inputs, stage


def change_policy(ctx):
    path = ctx.root / "configs/t0/tolerance_v1.yaml"
    data = read_yaml(path)
    data["max_variation"] = .01
    put_yaml(path, data)


def test_changed_policy_rejects_reference_before_writes(setup):
    ctx = setup()
    inputs(ctx)
    before = output_files(ctx.directory)
    change_policy(ctx)
    with pytest.raises(ValueError, match="^T0 tolerance policy mismatch$"):
        stage(ctx, "reference", checkpoint="checkpoint", runtime=ctx.runtime)
    assert output_files(ctx.directory) == before
    assert not (ctx.directory / "reference.jsonl").exists()


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("consumer", ["tolerance", "judge"])
def test_changed_policy_rejects_consumers_before_writes(setup, existing, consumer):
    ctx = setup()
    inputs(ctx)
    stage(ctx, "reference", checkpoint="checkpoint", runtime=ctx.runtime)
    stage(ctx, "server", base_url="http://127.0.0.1:1", post=fake_post())
    if existing:
        stage(ctx, "tolerance", rounding="reference=4")
        stage(ctx, "judge", rounding="reference=4,server=4")
    before = output_files(ctx.directory)
    change_policy(ctx)
    with pytest.raises(ValueError, match="^T0 tolerance policy mismatch$"):
        stage(ctx, consumer, rounding="reference=4,server=4")
    assert output_files(ctx.directory) == before
    assert (ctx.directory / "tolerance.json").exists() == existing
    assert (ctx.directory / "t0.json").exists() == existing
