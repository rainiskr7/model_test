"""무엇: 단계 파일 해시/누락/반올림 · 입력: 실제 생성 기록의 변조 · 출력: 거부/미완료 · 계약 T-a/g."""

import pytest

from jeveval.io.run_files import read_json, write_json
from jeveval.io.t0_files import read_lines, write_lines
from tests.t0_io.support import fake_post, inputs, stage, setup


def complete(ctx):
    inputs(ctx)
    stage(ctx, "reference", checkpoint="checkpoint", runtime=ctx.runtime)
    stage(ctx, "server", base_url="http://127.0.0.1:1", post=fake_post())
    stage(ctx, "tolerance", rounding="reference=4")


@pytest.mark.parametrize("file, field", [("reference", "inputs_sha256"), ("server", "request_sha256"),
    ("variants", "envelope_sha256"), ("variants", "target_sha256")])
def test_hash_chain_rejects_tampered_record(setup, file, field):
    ctx = setup()
    complete(ctx)
    path = ctx.directory / f"{file}.jsonl"
    header, rows = read_lines(path)
    rows[0][field] = {} if field == "target_sha256" else "0" * 64
    write_lines(path, header, rows)
    with pytest.raises(ValueError, match="hash|provenance"):
        stage(ctx, "judge", rounding="reference=4,server=4")


def test_tolerance_and_fingerprint_chain(setup):
    ctx = setup()
    complete(ctx)
    path = ctx.directory / "tolerance.json"
    record = read_json(path)
    record["reference_sha256"] = "0" * 64
    write_json(path, record)
    with pytest.raises(ValueError, match="provenance"):
        stage(ctx, "judge", rounding="reference=4,server=4")
    stage(ctx, "tolerance", rounding="reference=4")
    path = ctx.directory / "fingerprint.json"
    record = read_json(path)
    record["inputs_sha256"] = "0" * 64
    write_json(path, record)
    with pytest.raises(ValueError, match="provenance"):
        stage(ctx, "judge", rounding="reference=4,server=4")


def test_missing_server_is_incomplete_duplicate_is_error(setup):
    ctx = setup()
    complete(ctx)
    path = ctx.directory / "server.jsonl"
    header, rows = read_lines(path)
    write_lines(path, header, rows[:1])
    assert stage(ctx, "judge", rounding="reference=4,server=4")["status"] == "INCOMPLETE"
    write_lines(path, header, [rows[0], rows[0]])
    with pytest.raises(ValueError, match="duplicate"):
        stage(ctx, "judge", rounding="reference=4,server=4")


def test_missing_variant_is_unmeasured_and_rounding_cannot_change(setup):
    ctx = setup()
    complete(ctx)
    with pytest.raises(ValueError, match="rounding"):
        stage(ctx, "judge", rounding="reference=3,server=4")
    path = ctx.directory / "variants.jsonl"
    header, rows = read_lines(path)
    write_lines(path, header, rows[1:])
    stage(ctx, "tolerance", rounding="reference=4")
    assert stage(ctx, "judge", rounding="reference=4,server=4")["status"] == "INCOMPLETE"
    assert stage(ctx, "judge", rounding="reference=4,server=4", no_reference=True)["status"] == "PARTIAL"


