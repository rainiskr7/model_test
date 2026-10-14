"""Run the real expansion and writer with a local, fixed-response adapter."""

import json
from types import SimpleNamespace

from shared.functionchat.runner import run_functionchat as runner
from shared.jsonwrite.atomic_json import write_json_atomic


def test_main_writes_all_datasets_and_coverage(monkeypatch, tmp_path):
    bench = tmp_path / "data/FunctionChat-Bench/data"
    bench.mkdir(parents=True)
    (bench / "system_prompt.txt").write_text("합성 시스템 프롬프트", encoding="utf-8")
    messages = [{"role": "user", "content": "서울 날씨"}]
    truth = {"name": "weather", "arguments": '{"city": "서울"}'}
    inputs = {
        "Singlecall": {
            "query": [{"serial_num": 1, "content": "서울 날씨"}],
            "ground_truth": [{"content": json.dumps(truth, ensure_ascii=False)}],
            "acceptable_arguments": [{"content": None}],
            "tools": [{"type": "single", "content": []}],
        },
        "CallDecision": {
            "serial_num": 1, "type_of_output": "call", "input_messages": messages,
            "input_tools": [], "ground_truth": truth,
        },
        "Dialog": {
            "tools": [], "dialog_num": 1,
            "turns": [{
                "serial_num": 1, "turn_num": 1, "type_of_output": "call",
                "query": messages, "ground_truth": truth,
            }],
        },
    }
    for name, record in inputs.items():
        (bench / f"FunctionChat-{name}.jsonl").write_text(
            json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8",
        )

    calls = []
    preflights = []
    response = {"message": {"content": "고정 응답", "tool_calls": []}, "finish_reason": "stop"}

    class FakeAdapter:
        sdk_max_retries = 0
        openai_sdk_version = "synthetic"
        unparsed_tool_call_candidates = 0

        def __init__(self, model, **kwargs):
            def list_models(**kwargs):
                preflights.append(model)
                return SimpleNamespace(data=[SimpleNamespace(id=model)])

            self.client = SimpleNamespace(models=SimpleNamespace(list=list_models))

        def chat_completion(self, messages, *, tools):
            calls.append((messages, tools))
            return response

    monkeypatch.setenv("MODEL_TEST_BASE", str(tmp_path))
    monkeypatch.setenv("EVAL_TIMESTAMP", "session")
    monkeypatch.setattr(runner, "load_shared_adapter", lambda base: FakeAdapter)
    assert runner.write_json_atomic is write_json_atomic
    assert runner.main(["--model", "test/model", "--base-url", "http://unused.invalid/v1"]) == 0
    assert preflights == ["test/model"]
    assert len(calls) == 3
    output = tmp_path / "results/test_model/session/language/functionchat"
    assert {path.name for path in output.iterdir()} == {
        "singlecall.json", "call_decision.json", "dialog.json", "coverage.json",
    }
    for path in output.iterdir():
        raw = path.read_bytes()
        value = json.loads(raw)
        assert raw == (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if path.name != "coverage.json":
            assert value["metadata"]["total_items"] == 1
            assert value["metadata"]["measured_items"] == 1
            assert len(value["results"]) == 1
            assert value["results"][0]["raw_response"] == response
            assert value["results"][0]["error"] is None
    coverage = json.loads((output / "coverage.json").read_bytes())
    assert set(coverage["datasets"]) == {"singlecall", "call_decision", "dialog"}
    assert all(value["measured_items"] == 1 for value in coverage["datasets"].values())
    assert coverage["datasets"]["dialog"]["source_records"] == 1
