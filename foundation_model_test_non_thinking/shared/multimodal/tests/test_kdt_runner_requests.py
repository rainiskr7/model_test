"""K-DTC main request/storage anchors.

Excluded variable fields: run_config.timestamp_utc; sidecar completion timestamps
and artifact hashes. See _runner_fakes for pinned environment probes.
"""

import sys

import pytest

from shared.multimodal.tests.test_publish_native_runner import _load_kdt_runner
from shared.multimodal.tests._runner_fakes import (
    MC_PROMPTS, assert_requests, assert_storage, choice_rows, expected_choices,
    prepare,
)


@pytest.mark.parametrize("error,defaults", [(False, True), (False, False), (True, False)])
def test_main_requests_and_files(monkeypatch, tmp_path, capsys, error, defaults, fresh_import):
    runner = _load_kdt_runner(monkeypatch, fresh_import)
    responses = ["A", TimeoutError("synthetic timeout"), TimeoutError("synthetic timeout")] if error else ["A", "B"]
    state = prepare(monkeypatch, tmp_path, runner, choice_rows(), responses, defaults=defaults)
    assert runner.main() == 1  # two rows cannot satisfy the real 240-row full-run gate.
    assert capsys.readouterr().err == ""
    assert_requests(state, MC_PROMPTS + ([MC_PROMPTS[1]] if error else []),
                    [(255, 0, 0), (0, 0, 255)] + ([(0, 0, 255)] if error else []), defaults=defaults)
    assert state.sleeps == ([0.0] if error else [])
    records = assert_storage(
        state, runner, tmp_path, benchmark="K-DTCBench", dataset_id="NCSOFT/K-DTCBench",
        split="test", extra={"limit": None}, expected_count=240, error=error, defaults=defaults,
    )
    assert records == expected_choices(error=error)


@pytest.mark.parametrize("missing_fake", ["revision", "dataset", "transport"])
def test_main_fails_closed_if_external_fake_is_missing(monkeypatch, tmp_path, missing_fake, fresh_import):
    runner = _load_kdt_runner(monkeypatch, fresh_import)
    metadata = sys.modules[runner.build_run_config.__module__]
    client_module = sys.modules[runner.make_client.__module__]
    real_revision, real_openai = metadata.get_hf_dataset_revision, client_module.OpenAI
    state = prepare(monkeypatch, tmp_path, runner, choice_rows(), ["A", "B"])
    if missing_fake == "revision":
        # Real lookup reaches the forbidden HfApi.dataset_info boundary.
        monkeypatch.setattr(metadata, "get_hf_dataset_revision", real_revision)
    elif missing_fake == "dataset":
        monkeypatch.setattr(runner, "load_dataset", sys.modules["datasets"].load_dataset)
    else:
        monkeypatch.setattr(client_module, "OpenAI", real_openai)
    with pytest.raises(pytest.fail.Exception, match="unexpected live network/HF call"):
        runner.main()
    assert state.calls == []
    assert list(state.output.iterdir()) == []
