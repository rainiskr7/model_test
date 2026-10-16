"""공개 참조와 batch-one 판정, 변형 provenance 경계."""

import pytest

from jeveval.io.hashes import sha256_file
from jeveval.io.t0_files import read_lines
from jeveval.io.t0_inputs import load
from jeveval.run import t0_reference
from tests.run.cli_support import output_files
from tests.t0_io.conftest import inputs, setup


@pytest.mark.parametrize("mode,reason", [("equal", None), ("mismatch", "batch_one_mismatch"),
                                         ("unavailable", "batch_one_unavailable")])
def test_batch_one_controls_variants_and_header(setup, t0_policy, monkeypatch, mode, reason):
    ctx = setup(mismatch=mode == "mismatch")
    inputs(ctx)
    bundle = load(ctx.directory / "inputs.jsonl")
    if mode == "unavailable":
        def unavailable(*args):
            raise RuntimeError("synthetic batch failure")
        monkeypatch.setattr(t0_reference, "batch", unavailable)
    result = t0_reference.execute(ctx.directory, bundle, ctx.runtime,
                                  ctx.root / "checkpoint", "cpu", t0_policy)
    header, rows = read_lines(ctx.directory / "variants.jsonl")
    assert header == dict(schema="t0_variants/1", inputs_sha256=bundle.sha256, family="clef",
        reference_sha256=sha256_file(ctx.directory / "reference.jsonl"),
        tolerance_policy_sha256=t0_policy.sha256, batch_one_equal=mode == "equal", reason=reason)
    assert result["reason"] == reason
    expected = len(bundle.rows) * len(t0_policy.variants["clef"]) * t0_policy.repeats
    assert len(rows) == result["variants"] == (expected if mode == "equal" else 0)


def test_reference_family_mismatch_precedes_writes(setup, t0_policy):
    from dataclasses import replace
    ctx = setup()
    inputs(ctx)
    bundle = load(ctx.directory / "inputs.jsonl")
    before = output_files(ctx.directory)
    with pytest.raises(ValueError, match="^reference family mismatch$"):
        t0_reference.execute(ctx.directory, bundle, replace(ctx.runtime, family="pplx_v1"),
                              ctx.root / "checkpoint", "cpu", t0_policy)
    assert output_files(ctx.directory) == before
