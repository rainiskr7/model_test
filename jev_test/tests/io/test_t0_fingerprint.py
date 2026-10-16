"""T0 지문 초기화 및 참조 추가의 입력 결합."""

from dataclasses import replace

import pytest

from jeveval.io import t0_fingerprint
from jeveval.io.hashes import code_sha256
from jeveval.io.run_files import read_json
from jeveval.io.t0_inputs import load
from tests.run.cli_support import output_files
from tests.t0_io.conftest import inputs, setup


def test_initialize_records_declared_fields(setup):
    ctx = setup()
    inputs(ctx)
    bundle = load(ctx.directory / "inputs.jsonl")
    t0_fingerprint.initialize(ctx.directory, bundle, ctx.root)
    cfg = bundle.metadata["config"]
    assert read_json(ctx.directory / "fingerprint.json") == dict(schema="t0_fingerprint/1",
        inputs_sha256=bundle.sha256, fixture_sha256=bundle.metadata["fixture_sha256"],
        config_sha256=bundle.metadata["config_sha256"],
        tolerance_policy_sha256=bundle.metadata["tolerance_policy_sha256"],
        code_sha256=code_sha256(ctx.root), reference=None, server=dict(
            engine_version=cfg["serving"]["engine_version"], image_digest=cfg["serving"]["image_digest"],
            served_name=cfg["served_name"]))


def test_add_reference_rejects_input_mismatch_before_loading_or_writing(setup, monkeypatch):
    ctx = setup()
    inputs(ctx)
    bundle = replace(load(ctx.directory / "inputs.jsonl"), sha256="0" * 64)
    before = output_files(ctx.directory)
    def forbidden(*args):
        pytest.fail("mismatched inputs reached reference inspection")
    monkeypatch.setattr(t0_fingerprint, "reference_fingerprint", forbidden)
    with pytest.raises(ValueError, match="^fingerprint inputs mismatch$"):
        t0_fingerprint.add_reference(ctx.directory, bundle, ctx.runtime, ctx.root / "checkpoint", "cpu")
    assert output_files(ctx.directory) == before
