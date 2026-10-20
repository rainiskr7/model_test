"""무엇: T0 reference 길이 검증 · 입력: null limit inputs/주입 runtime · 출력: 참조 실행 전 거부 · 계약 §8-7."""

import pytest

from jeveval.io.config import read_yaml
from jeveval.run import cmd_t0
from tests.run.file_support import output_files, put_yaml
from .support import inputs, stage


@pytest.mark.parametrize("family", ["clef", "clef_flash", "pplx_v1", "pplx_v1_1"])
@pytest.mark.parametrize("injected", [False, True])
def test_null_limit_inputs_allowed_but_reference_rejected(setup, monkeypatch, family, injected):
    ctx = setup(family)
    model_path = ctx.root / f"{family}.yaml"
    cfg = read_yaml(model_path)
    cfg["limit"]["tokens"] = None
    put_yaml(model_path, cfg)
    assert inputs(ctx)["ok"] is True
    before = output_files(ctx.directory)

    def forbidden(*args, **kwargs):
        pytest.fail("null limit reached reference loading or execution")

    monkeypatch.setattr(cmd_t0.t0_runner, "load", forbidden)
    monkeypatch.setattr(cmd_t0.t0_reference, "execute", forbidden)
    runtime = {"runtime": ctx.runtime} if injected else {}
    with pytest.raises(ValueError, match="^limit.tokens is required for reference execution$"):
        stage(ctx, "reference", checkpoint="checkpoint", **runtime)
    assert output_files(ctx.directory) == before
