"""K-MM main with actual A-D schema, hints and category/head selection.

Excluded variable fields: run_config.timestamp_utc; sidecar completion timestamps
and artifact hashes. Environment probes are fixed in _runner_fakes.
"""

import pytest

from shared.multimodal.tests._runner_fakes import (
    MC_PROMPTS, assert_requests, assert_storage, choice_rows, expected_choices,
    load_runner, offline_guard, prepare,
)


@pytest.mark.parametrize("selected,error", [(False, False), (True, False), (True, True)])
def test_main_requests_and_files(monkeypatch, tmp_path, capsys, selected, error, fresh_import):
    offline_guard(monkeypatch)
    runner = load_runner(fresh_import, "k_mmbench")
    rows = choice_rows(kmm=True)
    extra = []
    if selected:
        # Drop an unrelated category, then drop a third retained row using head.
        rows += [{**rows[0], "index": "drop-head"}, {**rows[0], "category": "drop-category"}]
        extra = ["--categories", "document,chart", "--limit", "2", "--sample-mode", "head"]
    responses = ["A", TimeoutError("synthetic timeout"), TimeoutError("synthetic timeout")] if error else ["A", "B"]
    state = prepare(monkeypatch, tmp_path, runner, rows, responses, extra=extra)
    assert runner.main() == (0 if selected and not error else 1)
    assert capsys.readouterr().err == ""
    prompts = ["Hint: 힌트\n\n" + MC_PROMPTS[0], MC_PROMPTS[1]]
    assert_requests(state, prompts + ([prompts[1]] if error else []),
                    [(255, 0, 0), (0, 0, 255)] + ([(0, 0, 255)] if error else []))
    assert state.sleeps == ([0.0] if error else [])
    records = assert_storage(
        state, runner, tmp_path, benchmark="K-MMBench", dataset_id="NCSOFT/K-MMBench",
        split="dev", extra={"categories_filter": "document,chart" if selected else None,
                            "limit": 2 if selected else None, "sample_mode": "head" if selected else "stratified"},
        expected_count=2 if selected else 4329, error=error,
    )
    assert records == expected_choices(kmm=True, error=error)
