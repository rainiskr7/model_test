"""T0 서버 경계: 인증, 단일 시도 timeout, 관측 봉투."""

import pytest

from jeveval.io.t0_files import read_lines
from jeveval.io.t0_inputs import load
from jeveval.run import t0_server
from tests.run.cli_support import output_files
from tests.t0_io.conftest import fake_post, inputs, setup


@pytest.mark.parametrize("secret", [None, "", "bad\nkey", "한글"])
def test_auth_failure_precedes_transmission_and_writes(setup, monkeypatch, secret):
    ctx = setup()
    inputs(ctx)
    bundle = load(ctx.directory / "inputs.jsonl")
    if secret is None:
        monkeypatch.delenv("T0_TEST_AUTH")
    else:
        monkeypatch.setenv("T0_TEST_AUTH", secret)
    post, before = fake_post(), output_files(ctx.directory)
    with pytest.raises(ValueError, match="^authentication unavailable$"):
        t0_server.execute(ctx.directory, bundle, "http://127.0.0.1:1", post=post)
    assert post.calls == [] and output_files(ctx.directory) == before


def test_timeout_is_not_retried_and_observation_preserves_envelope(setup):
    ctx = setup()
    inputs(ctx)
    bundle = load(ctx.directory / "inputs.jsonl")
    observed, fake = [], fake_post("timeout")
    def post(url, payload, timeout, headers):
        observed.append((timeout, headers))
        return fake(url, payload, timeout, headers)
    result = t0_server.execute(ctx.directory, bundle, "http://127.0.0.1:1", timeout=17, post=post)
    assert result == {"ok": True, "cases": len(bundle.rows)}
    assert observed == [(17, {"Authorization": "Bearer secret_auth_canary"})] * len(bundle.rows)
    header, rows = read_lines(ctx.directory / "server.jsonl")
    assert header == {"schema": "t0_server/1", "inputs_sha256": bundle.sha256}
    assert rows[0]["transport_error"] == "timeout" and rows[0]["http_status"] is None
    assert rows[1]["transport_error"] is None and rows[1]["http_status"] == 200
    for source, record in zip(bundle.rows, rows, strict=True):
        assert record["case_id"] == source.case_id
        assert record["inputs_sha256"] == bundle.sha256
        assert record["request_sha256"] == source.request_sha256
        assert record["envelope_sha256"] == source.envelope_sha256
        assert set(record) == {"case_id", "inputs_sha256", "request_sha256", "envelope_sha256",
            "http_status", "response_raw", "transport_error", "length_status", "latency_ms", "response_bytes"}
