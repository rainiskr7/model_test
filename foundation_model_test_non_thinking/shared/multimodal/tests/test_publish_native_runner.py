from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

from shared.multimodal.publish.adapters import adapt_accuracy, summarize_records
from shared.multimodal.publish.derive import native_sidecar_from_records, preflight_kreta_source


REPO = Path(__file__).resolve().parents[3]
BENCHES = REPO / "shared/multimodal/benches"


def test_summarize_records_clean_has_equal_strict_and_conditional():
    rows = [
        {"response": "A", "answer": "A", "category": "document"},
        {"response": "B", "answer": "A", "category": "document"},
    ]
    summary = summarize_records("k_dtcbench", rows, expected_count=2)
    assert summary["publish_status"] == {"publishable": True, "failures": []}
    assert summary["counts"] == {
        "attempted": 2,
        "measured": 2,
        "errored": 0,
        "unresolved": 0,
        "correct_measured": 1,
    }
    assert summary["accuracy_strict"] == summary["accuracy_conditional"]


def test_summarize_records_errors_reduce_only_conditional_denominator():
    rows = [
        {"response": "A", "answer": "A", "correct": True},
        {"response": {"error": "timeout"}, "answer": "A", "correct": True, "error": "timeout"},
        {"response": "{'error': 설명}", "answer": "B", "correct": False},
    ]
    summary = summarize_records("k_dtcbench", rows, expected_count=3)
    assert summary["publish_status"]["publishable"] is False
    assert summary["counts"]["measured"] == 2
    assert summary["counts"]["errored"] == 1
    assert summary["counts"]["correct_measured"] == 1
    assert summary["accuracy_strict"]["denominator"] == 3
    assert summary["accuracy_conditional"]["denominator"] == 2


def test_clean_completed_source_is_promoted_to_native(monkeypatch, tmp_path):
    from shared.multimodal.publish import adapters

    monkeypatch.setitem(adapters.EXPECTED_COUNTS, "k_dtcbench", 2)
    source_dir = tmp_path / "results/model/session/vision/multimodal/k_dtcbench"
    source_dir.mkdir(parents=True)
    rows = [
        {"index": "a", "category": "document", "response": "A", "answer": "A"},
        {"index": "b", "category": "document", "response": "B", "answer": "A"},
    ]
    aggregate = summarize_records("k_dtcbench", rows, expected_count=2)
    summary = {
        "model": "model",
        "total": 2,
        "correct": aggregate["correct"],
        "accuracy": aggregate["accuracy"],
        "by_category": aggregate["by_category"],
        "run_config": {
            "timestamp_utc": "2026-01-01T00:00:00+00:00",
            "model": {"name": "model"},
            "dataset": {"huggingface_id": "NCSOFT/K-DTCBench", "revision": "revision"},
            "decoding": {"temperature": 0.0, "max_tokens": 512, "seed": None},
            "extra": {"limit": None},
        },
    }
    (source_dir / "results.json").write_text(json.dumps(rows), encoding="utf-8")
    (source_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    _, sidecar = native_sidecar_from_records(
        source_dir,
        tmp_path,
        rows,
        benchmark_id="k_dtcbench",
        expected_count=2,
    )
    assert sidecar["status"] == "NATIVE"
    assert sidecar["publishable"] is True


def test_kreta_preflight_blocks_typed_error_before_evaluate(monkeypatch, tmp_path):
    from shared.multimodal.publish import adapters

    monkeypatch.setitem(adapters.EXPECTED_COUNTS, "kreta", 2)
    source = tmp_path / "results/model/session/vision/multimodal/kreta/model_direct.jsonl"
    source.parent.mkdir(parents=True)
    rows = [
        {"id": "a", "response": "A", "pred_indexs": "A", "answer": "A"},
        {"id": "b", "response": {"error": "timeout"}, "pred_indexs": "A", "answer": "A", "if_right": True},
    ]
    source.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    ok, failures = preflight_kreta_source(source, tmp_path)
    assert ok is False
    assert "오류 응답 1건 포함" in failures


class _TinyDataset:
    def __init__(self, rows):
        self.rows = list(rows)

    def __iter__(self):
        return iter(self.rows)

    def __len__(self):
        return len(self.rows)

    def select(self, indexes):
        return _TinyDataset(self.rows[index] for index in indexes)


def _load_kdt_runner(monkeypatch):
    fake_datasets = types.ModuleType("datasets")
    fake_datasets.load_dataset = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "datasets", fake_datasets)
    monkeypatch.syspath_prepend(str(BENCHES))
    spec = importlib.util.spec_from_file_location("test_k_dtcbench_runner", BENCHES / "k_dtcbench.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_kdt_runner_writes_rejected_native_gate_and_adapter_reaggregates(monkeypatch, tmp_path):
    runner = _load_kdt_runner(monkeypatch)
    rows = [
        {
            "index": "document_0",
            "category": "document",
            "question": "q0",
            "choice_a": "a",
            "choice_b": "b",
            "choice_c": "c",
            "choice_d": "d",
            "answer": "A",
            "image": object(),
        },
        {
            "index": "document_1",
            "category": "document",
            "question": "q1",
            "choice_a": "a",
            "choice_b": "b",
            "choice_c": "c",
            "choice_d": "d",
            "answer": "A",
            "image": object(),
        },
    ]
    source_dir = tmp_path / "results/model/session/vision/multimodal/k_dtcbench"
    source_dir.mkdir(parents=True)
    monkeypatch.setattr(runner, "load_dataset", lambda *args, **kwargs: _TinyDataset(rows))
    monkeypatch.setattr(runner, "get_base_dir", lambda _: tmp_path)
    monkeypatch.setattr(runner, "get_timestamp", lambda _: "session")
    monkeypatch.setattr(runner, "get_results_dir", lambda *args, **kwargs: source_dir)
    monkeypatch.setattr(runner, "resolve_dataset_revision", lambda *args: ("revision", "test"))
    monkeypatch.setattr(runner, "make_client", lambda *args: object())
    calls = iter(["A", RuntimeError("synthetic failure")])

    def fake_chat(*args, **kwargs):
        value = next(calls)
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr(runner, "chat_with_image", fake_chat)
    monkeypatch.setattr(runner, "EXPECTED_COUNT", 2)
    monkeypatch.setattr(
        runner,
        "build_run_config",
        lambda **kwargs: {
            "timestamp_utc": "2026-01-01T00:00:00+00:00",
            "model": {"name": "model"},
            "dataset": {"huggingface_id": "NCSOFT/K-DTCBench", "revision": "revision"},
            "decoding": {"temperature": 0.0, "max_tokens": 512, "seed": None},
            "extra": {"limit": None},
        },
    )
    from shared.multimodal.publish import adapters

    monkeypatch.setitem(adapters.EXPECTED_COUNTS, "k_dtcbench", 2)
    monkeypatch.setattr(sys, "argv", ["k_dtcbench.py", "--model", "model"])

    assert runner.main() == 1
    raw = json.loads((source_dir / "results.json").read_text(encoding="utf-8"))
    summary = json.loads((source_dir / "summary.json").read_text(encoding="utf-8"))
    sidecar = json.loads((source_dir / "_derived/publish.json").read_text(encoding="utf-8"))
    assert raw[1]["response"] == {"error": "synthetic failure"}
    assert summary["counts"]["errored"] == 1
    assert summary["publish_status"]["publishable"] is False
    assert sidecar["status"] == "REJECTED"

    reaggregated = adapt_accuracy(source_dir, "k_dtcbench")
    assert reaggregated["counts"] == summary["counts"]
    assert reaggregated["metrics"]["strict"] == summary["accuracy_strict"]
    assert reaggregated["metrics"]["conditional"] == summary["accuracy_conditional"]
