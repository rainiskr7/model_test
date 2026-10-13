"""B3 pre-refactor anchors; variable fields are listed in _r3_runner_fakes."""

import json

import pytest

pytest.register_assert_rewrite("_runner_fakes")

from _runner_fakes import assert_requests, load_runner, png, read_json
from _r3_runner_fakes import arguments, assert_capture, capture, cli, prepare_local


@pytest.mark.parametrize("mode", ["valid", "invalid", "error", "missing"])
def test_main_requests_storage_rc(monkeypatch, tmp_path, capsys, mode):
    runner = load_runner(monkeypatch, "b3_structured_output")
    png("red").save(tmp_path / "tiny.png")
    manifest = tmp_path / "manifest.json"
    expected = {"type": "object", "required_fields": ["합계"],
                "value_checks": [{"path": "$.합계", "value": 5}]}
    manifest.write_text(json.dumps([
        {"id": "one", "category": "table", "image": "tiny.png", "prompt": "합계 JSON", "expected": expected},
        {"id": "two", "category": "receipt", "image": "absent.png" if mode == "missing" else "tiny.png",
         "prompt": "두 번째 JSON", "expected": expected},
    ], ensure_ascii=False), encoding="utf-8")
    responses = ['{"합계": 5}', {"valid": '{"합계": 3}', "invalid": "invalid JSON",
                 "missing": "unused", "error": ValueError("invalid request")}[mode]]
    state = prepare_local(monkeypatch, tmp_path, responses)
    cli(monkeypatch, arguments("--manifest", str(manifest)))
    rc = runner.main()
    assert rc == (1 if mode in ("missing", "error") else 0)
    output = tmp_path / "results/test_model_a_1/r3-session/vision/customB/b3_structured_output"
    records = read_json(output / "results.json")
    assert records[0]["parse_ok"] is True
    assert records[0]["schema_check"] == {"required_fields_present": True, "missing_fields": [], "type_match": True}
    assert records[0]["value_check"]["match_rate"] == 1.0
    assert_requests(state, ["합계 JSON"] + ([] if mode == "missing" else ["두 번째 JSON"]),
                    [(255, 0, 0)] * (1 if mode == "missing" else 2))
    assert all("response_format" not in call for call in state.calls)
    assert_capture("b3_" + mode, capture(output, rc, state, capsys), tmp_path)
