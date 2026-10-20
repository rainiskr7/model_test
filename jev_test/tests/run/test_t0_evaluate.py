"""허용폭/판정 결과의 provenance 및 저장된 정책 해시 검증."""

import pytest

from jeveval.io.hashes import sha256_file
from jeveval.io.run_files import read_json, write_json
from jeveval.io.t0_inputs import load
from jeveval.run import t0_evaluate
from tests.run.file_support import output_files
from tests.t0_io.support import fake_post, inputs, setup, stage


def prepared(setup, t0_policy):
    ctx = setup()
    inputs(ctx)
    stage(ctx, "reference", checkpoint="checkpoint", runtime=ctx.runtime)
    stage(ctx, "server", base_url="http://127.0.0.1:1", post=fake_post())
    bundle = load(ctx.directory / "inputs.jsonl")
    t0_evaluate.tolerance(ctx.directory, bundle, "reference=4", t0_policy)
    return ctx, bundle


def test_tolerance_and_judgement_provenance_fields(setup, t0_policy):
    ctx, bundle = prepared(setup, t0_policy)
    measured = read_json(ctx.directory / "tolerance.json")
    expected = dict(inputs_sha256=bundle.sha256, tolerance_policy_sha256=t0_policy.sha256,
        reference_sha256=sha256_file(ctx.directory / "reference.jsonl"),
        variants_sha256=sha256_file(ctx.directory / "variants.jsonl"))
    assert {key: measured[key] for key in expected} == expected
    assert measured["rounding"] == 4
    result = t0_evaluate.evaluate(ctx.directory, bundle, "reference=4,server=4", False, t0_policy)
    assert result["status"] == "PASS"
    record = read_json(ctx.directory / "t0.json")
    assert {key: record[key] for key in expected} == expected
    for field, name in [("tolerance_sha256", "tolerance.json"), ("server_sha256", "server.jsonl"),
                        ("fingerprint_sha256", "fingerprint.json")]:
        assert record[field] == sha256_file(ctx.directory / name)


@pytest.mark.parametrize("existing", [False, True])
def test_stored_tolerance_policy_hash_mismatch_precedes_judgement_write(setup, t0_policy, existing):
    ctx, bundle = prepared(setup, t0_policy)
    if existing:
        t0_evaluate.evaluate(ctx.directory, bundle, "reference=4,server=4", False, t0_policy)
    path = ctx.directory / "tolerance.json"
    data = read_json(path)
    data["tolerance_policy_sha256"] = "0" * 64
    write_json(path, data)
    before = output_files(ctx.directory)
    with pytest.raises(ValueError, match="^T0 tolerance provenance mismatch$"):
        t0_evaluate.evaluate(ctx.directory, bundle, "reference=4,server=4", False, t0_policy)
    assert output_files(ctx.directory) == before
