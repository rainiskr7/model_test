"""Synthetic fixtures and contracts captured from the pre-extraction runner."""

import hashlib
import io
import json
from contextlib import redirect_stderr, redirect_stdout
from types import SimpleNamespace

import pytest

from shared.functionchat.runner import run_functionchat as runner


def _inputs(directory):
    directory.mkdir(parents=True)
    (directory / "system_prompt.txt").write_text("  합성 시스템  \n", encoding="utf-8")
    truth = {"name": "weather", "arguments": '{"city":"서울"}'}
    tools = [{"type": "function", "function": {"name": "weather", "parameters": {}}}]
    messages = [{"role": "user", "content": "서울 날씨"}]
    records = {
        "Singlecall": [{
            "query": [{"serial_num": 1, "content": "서울 날씨"}],
            "ground_truth": [{"content": json.dumps(truth)}],
            "acceptable_arguments": [{"content": None}],
            "tools": [{"type": "single", "content": tools}],
        }],
        "CallDecision": [
            {"serial_num": n, "type_of_output": kind, "input_messages": messages,
             "input_tools": tools, "ground_truth": truth}
            for n, kind in enumerate(("call", "slot"), 1)
        ],
        "Dialog": [{"tools": tools, "dialog_num": 1, "turns": [
            {"serial_num": n, "turn_num": n, "type_of_output": kind,
             "query": messages, "ground_truth": truth}
            for n, kind in enumerate(("call", "relevance"), 1)
        ]}],
    }
    for name, items in records.items():
        (directory / f"FunctionChat-{name}.jsonl").write_text(
            "\n".join(json.dumps(item) for item in items) + "\n", encoding="utf-8"
        )


def test_load_datasets_preserves_order_and_messages(tmp_path):
    _inputs(tmp_path / "inputs")
    datasets = runner._load_datasets(tmp_path / "inputs")
    assert list(datasets) == ["singlecall", "call_decision", "dialog"]
    assert [len(items) for items in datasets.values()] == [1, 2, 2]
    assert datasets["singlecall"][0]["messages"] == [
        {"role": "system", "content": "합성 시스템"},
        {"role": "user", "content": "서울 날씨"},
    ]
    assert [item["type_of_output"] for item in datasets["dialog"]] == ["call", "relevance"]


@pytest.mark.parametrize("limit,truncated,lengths", [(1, True, [1, 1, 1]), (9, False, [1, 2, 2])])
def test_select_datasets_keeps_prefix_without_mutating_input(limit, truncated, lengths):
    datasets = {"singlecall": [1], "call_decision": [2, 3], "dialog": [4, 5]}
    selected, actual = runner._select_datasets(datasets, limit)
    assert actual is truncated
    assert list(selected) == list(datasets)
    assert [len(items) for items in selected.values()] == lengths
    assert [items[0] for items in selected.values()] == [1, 2, 4]
    assert datasets == {"singlecall": [1], "call_decision": [2, 3], "dialog": [4, 5]}


@pytest.mark.parametrize("empty", [False, True])
def test_build_coverage_counts_turns_and_sorted_unmeasured_types(empty):
    datasets = {
        "singlecall": [{"type_of_output": "call"}],
        "call_decision": [{"type_of_output": "slot"}],
        "dialog": [{"type_of_output": kind} for kind in ("slot", "call", "relevance", "slot")],
    }
    if empty:
        datasets = {name: [] for name in datasets}
    coverage = runner._build_coverage(datasets, 7)
    assert coverage == {
        "source": {"repository": "kakao/FunctionChat-Bench", "commit": runner.SOURCE_COMMIT},
        "datasets": {
            "singlecall": {"source_lines": 25, "expanded_items": 0 if empty else 1,
                           "measured_items": 0 if empty else 1},
            "call_decision": {"source_lines": 0 if empty else 1, "measured_items": 0},
            "dialog": {"source_records": 7, "expanded_items": 0 if empty else 4,
                       "measured_items": 0 if empty else 1},
        },
        "not_measured": {
            "call_decision": {"relevance": 0, "slot": 0 if empty else 1},
            "dialog": {} if empty else {"relevance": 1, "slot": 2},
        },
    }
    assert list(coverage["not_measured"]["dialog"]) == ([] if empty else ["relevance", "slot"])


def _main_contract(monkeypatch, tmp_path, scenario):
    """Capture requests, all saved bytes, logs and rc with a fixed clock and no network."""
    _inputs(tmp_path / "data/FunctionChat-Bench/data")
    monkeypatch.setenv("MODEL_TEST_BASE", str(tmp_path))
    monkeypatch.setenv("EVAL_TIMESTAMP", "session")
    monkeypatch.setenv("AGENT_NATIVE_TOOL_CALLING", "0")
    monkeypatch.setattr(runner, "datetime", SimpleNamespace(
        now=lambda: SimpleNamespace(isoformat=lambda: "2000-01-02T03:04:05")
    ))
    monkeypatch.setattr(runner.time, "monotonic", lambda: 10.0)
    monkeypatch.setattr(runner, "_load_effective_decoding", lambda: None)
    calls = []

    class Adapter:
        sdk_max_retries = 0
        openai_sdk_version = "fixed"
        unparsed_tool_call_candidates = 0

        def __init__(self, model, **kwargs):
            calls.append(["init", model, kwargs])

            def models(**kwargs):
                calls.append(["models", kwargs])
                return SimpleNamespace(data=[SimpleNamespace(
                    id="absent" if scenario == "preflight_failure" else model
                )])

            self.client = SimpleNamespace(models=SimpleNamespace(list=models))

        def chat_completion(self, messages, *, tools):
            calls.append(["chat", messages, tools])
            if scenario == "request_failure":
                raise RuntimeError("synthetic failure")
            return {"message": {"content": "고정 응답", "tool_calls": []},
                    "finish_reason": "stop", "usage": {"total_tokens": 3}}

    monkeypatch.setattr(runner, "load_shared_adapter", lambda base: Adapter)
    args = ["--model", "test/model", "--base-url", "http://unused.invalid/v1",
            "--request-timeout", "3", "--task-timeout", "9", "--max-tokens", "17",
            "--native-tool-calling"]
    if scenario.startswith("limit"):
        args += ["--limit", "1" if scenario == "limit_short" else "9"]
    stdout, stderr = io.StringIO(), io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        rc = runner.main(args)
    assert rc == (2 if scenario == "preflight_failure" else 0)
    chat_count = sum(call[0] == "chat" for call in calls)
    assert chat_count == {"preflight_failure": 0, "limit_short": 3, "request_failure": 10}.get(scenario, 5)
    files = {p.relative_to(tmp_path).as_posix(): p.read_bytes().decode("utf-8")
             for p in sorted((tmp_path / "results").rglob("*.json"))}
    value = {"rc": rc, "calls": calls, "files": files,
             "stdout": stdout.getvalue().replace(str(tmp_path), "<ROOT>"),
             "stderr": stderr.getvalue().replace(str(tmp_path), "<ROOT>")}
    return hashlib.sha256(json.dumps(value, ensure_ascii=False).encode()).hexdigest()


# These hashes were captured by executing the original main, before extraction.
@pytest.mark.parametrize("scenario,expected", [
    ("success", "6697bab99d8dae19bbdefe9623037d426e3db8b254ebdb1f3259f3211b98eae7"),
    ("limit_short", "2f03c2a8cf0adb7701134301390a79d48309093a2793e511f644bd31754189b3"),
    ("limit_full", "f6c5664a05e63c2edc8f755fdf411288346808526e7dd6ca959553acf1281981"),
    ("preflight_failure", "717ec48ec2aa2855cbc0bde7bc4dacdf8e0803e2cb265a9fbe8a06848f4fca8d"),
    ("request_failure", "741f459d6e2d121df0bf1186326ccbdaed19dc2d1633bdfa302c2a130944d474"),
])
def test_main_request_storage_stdout_and_rc_contract(monkeypatch, tmp_path, scenario, expected):
    assert _main_contract(monkeypatch, tmp_path, scenario) == expected
