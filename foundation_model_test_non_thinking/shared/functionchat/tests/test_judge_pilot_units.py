"""9-1a pilot contracts captured before extraction; all IO stays in tmp_path."""

from pathlib import Path

import pytest

from shared.functionchat.judge import judge_pilot as pilot
from shared.multimodal.tests._runner_fakes import offline_guard


PILOT_BYTES = '''{
  "results_dir": "input",
  "per_type": 15,
  "seed": 42,
  "repeats": 2,
  "models": [
    "weak",
    "strong"
  ],
  "records": [
    {
      "serial_num": "s1",
      "dataset": "synthetic",
      "type_of_output": "slot",
      "judges": {
        "weak": [
          {
            "verdict": "pass"
          },
          {
            "verdict": "pass"
          }
        ],
        "strong": [
          {
            "verdict": "pass"
          }
        ]
      }
    }
  ]
}'''.encode("utf-8")


@pytest.fixture
def inputs(monkeypatch, tmp_path):
    offline_guard(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PILOT_UNIT_KEY", "synthetic-key")
    items = [{"serial_num": "s1", "dataset": "synthetic", "type_of_output": "slot",
              "messages": "질문"}]
    monkeypatch.setattr(pilot, "load_rubrics", lambda path: {"slot": "{query}"})
    monkeypatch.setattr(pilot, "collect_items", lambda path: items)
    return items, ["--results-dir", "input", "--out", "output/pilot.json",
                   "--api-key-env", "PILOT_UNIT_KEY", "--repeats", "2",
                   "--models", " weak, ,strong "]


def test_main_patched_judge_and_identity_reach_each_repeat(inputs, monkeypatch, capsys):
    _, args = inputs
    identities, calls = [], []

    def identity_factory():
        identity = object()
        identities.append(identity)
        return identity

    def judge(prompt, model, api_key, timeout, retries, *, identity):
        calls.append((prompt, model, api_key, timeout, retries, identity))
        return {"verdict": "pass"}

    monkeypatch.setattr(pilot, "ServedIdentity", identity_factory)
    monkeypatch.setattr(pilot, "call_judge", judge)
    for invocation in range(2):
        assert pilot.main(args) == 0
        assert Path("output/pilot.json").read_bytes() == PILOT_BYTES
        assert capsys.readouterr() == (
            "[judge-pilot] 대상 1건 중 층화 표본 1건, 모델 ['weak', 'strong']\n"
            "[judge-pilot] 1/1\n[judge-pilot] wrote output/pilot.json\n", "",
        )
        assert calls[invocation * 3:] == [
            ('"질문"', "weak", "synthetic-key", 120.0, 3, identities[invocation]),
            ('"질문"', "weak", "synthetic-key", 120.0, 3, identities[invocation]),
            ('"질문"', "strong", "synthetic-key", 120.0, 3, identities[invocation]),
        ]
    assert len(identities) == 2 and identities[0] is not identities[1]


def test_missing_key_keeps_string_system_exit_before_loading(inputs, monkeypatch, capsys):
    _, args = inputs
    monkeypatch.delenv("PILOT_UNIT_KEY")
    monkeypatch.setattr(pilot, "load_rubrics", lambda path: pytest.fail("loaded before key check"))
    with pytest.raises(SystemExit) as caught:
        pilot.main(args)
    assert caught.value.code == "PILOT_UNIT_KEY 환경변수가 필요합니다 (값은 인자로 받지 않습니다)."
    assert capsys.readouterr() == ("", "")
    assert not Path("output").exists()


def test_judge_failure_keeps_partial_progress_and_previous_file(inputs, monkeypatch, capsys):
    items, args = inputs
    items[:] = [dict(items[0], serial_num=str(n)) for n in range(6)]
    Path("output").mkdir()
    Path("output/pilot.json").write_bytes(b"previous\n")
    calls = []
    failure = RuntimeError("synthetic judge failure")

    def judge(*args, **kwargs):
        calls.append(args)
        if len(calls) == 6:
            raise failure
        return {"verdict": "pass"}

    monkeypatch.setattr(pilot, "call_judge", judge)
    with pytest.raises(RuntimeError) as caught:
        pilot.main([*args, "--models", "weak", "--repeats", "1"])
    assert caught.value is failure
    assert len(calls) == 6
    assert capsys.readouterr() == (
        "[judge-pilot] 대상 6건 중 층화 표본 6건, 모델 ['weak']\n[judge-pilot] 5/6\n", "",
    )
    assert Path("output/pilot.json").read_bytes() == b"previous\n"


def test_parse_args_preserves_defaults_and_path_types():
    assert vars(pilot._parse_args(["--results-dir", "input", "--out", "pilot.json"])) == {
        "results_dir": Path("input"), "out": Path("pilot.json"),
        "data_dir": Path("data/FunctionChat-Bench/data"), "per_type": 15, "seed": 42,
        "repeats": 3, "models": "openai/gpt-4.1-mini,openai/gpt-4.1",
        "api_key_env": "TAUBENCH_USER_API_KEY", "timeout": 120.0, "retries": 3,
    }
