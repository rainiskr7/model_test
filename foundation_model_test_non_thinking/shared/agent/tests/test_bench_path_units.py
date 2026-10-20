"""9-0 contracts captured from bench_path; all paths belong to tmp_path."""

import sys

import pytest

from shared.agent.scoring import bench_path


@pytest.fixture(autouse=True)
def isolated_search_path(monkeypatch):
    monkeypatch.setattr(sys, "path", list(sys.path))


@pytest.mark.parametrize("value", [None, ""])
def test_missing_base_preserves_search_path(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("MODEL_TEST_BASE", raising=False)
    else:
        monkeypatch.setenv("MODEL_TEST_BASE", value)
    before = list(sys.path)
    with pytest.raises(RuntimeError) as caught:
        bench_path.ensure_bench_path()
    assert str(caught.value) == (
        "MODEL_TEST_BASE is required to locate data/Ko-AgentBench for agent scoring"
    )
    assert sys.path == before


def test_missing_metrics_preserves_search_path(monkeypatch, tmp_path):
    monkeypatch.setenv("MODEL_TEST_BASE", str(tmp_path))
    before = list(sys.path)
    with pytest.raises(RuntimeError) as caught:
        bench_path.ensure_bench_path()
    assert str(caught.value) == (
        f"Ko-AgentBench metrics.py not found under {tmp_path}/data/Ko-AgentBench. "
        "Run shared/agent/install.sh or set MODEL_TEST_BASE correctly."
    )
    assert sys.path == before


@pytest.mark.parametrize("already_present", [False, True])
def test_valid_path_is_inserted_once_without_reordering(monkeypatch, tmp_path, already_present):
    checkout = tmp_path / "data/Ko-AgentBench"
    metrics = checkout / "bench/runner/metrics.py"
    metrics.parent.mkdir(parents=True)
    metrics.write_text("# synthetic marker; never imported\n", encoding="utf-8")
    monkeypatch.setenv("MODEL_TEST_BASE", str(tmp_path / "unused/.."))
    if already_present:
        sys.path.append(str(checkout))
    before = list(sys.path)
    assert bench_path.ensure_bench_path() == checkout
    assert bench_path.ensure_bench_path() == checkout
    assert sys.path == (before if already_present else [str(checkout), *before])
    assert sys.path.count(str(checkout)) == 1
