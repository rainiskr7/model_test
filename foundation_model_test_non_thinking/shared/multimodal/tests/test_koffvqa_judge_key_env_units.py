"""4c key selection through main, with fake workbook IO and client creation."""

import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture
def judge_run(monkeypatch, tmp_path, fresh_import):
    judge = fresh_import("shared.multimodal.benches.koffvqa_api_judge")
    predfile = tmp_path / "synthetic.xlsx"
    predfile.write_bytes(b"synthetic workbook")
    load = Mock(return_value=judge.pd.DataFrame(columns=["question", "answer", "prediction"]))
    monkeypatch.setattr(judge.pd, "read_excel", load)
    client = Mock(return_value=object())
    monkeypatch.setitem(sys.modules, "shared.multimodal.benches.common", SimpleNamespace(
        get_base_dir=lambda path: tmp_path, get_timestamp=lambda: "session",
        get_results_dir=lambda *args, **kwargs: tmp_path / "output",
        save_json=Mock(), build_run_config=lambda **kwargs: {}, make_client=client,
    ))
    argv = ["koffvqa_api_judge", "--predfile", str(predfile), "--target-model", "target",
            "--judge-model", "judge", "--judge-base-url", "https://unused.invalid/v1"]
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-fallback-key")
    monkeypatch.delenv("TEST_JUDGE_KEY", raising=False)
    return SimpleNamespace(judge=judge, argv=argv, client=client, load=load)


def test_named_environment_key_reaches_client(judge_run, monkeypatch):
    monkeypatch.setenv("TEST_JUDGE_KEY", "synthetic-env-key")
    judge_run.argv += ["--judge-api-key-env", "TEST_JUDGE_KEY"]
    assert judge_run.judge.main() == 10  # Key accepted; the synthetic workbook is empty.
    judge_run.client.assert_called_once_with("https://unused.invalid/v1", "synthetic-env-key")


@pytest.mark.parametrize("value", [None, ""])
def test_missing_or_empty_named_key_fails_without_fallback(judge_run, monkeypatch, capsys, value):
    if value is not None:
        monkeypatch.setenv("TEST_JUDGE_KEY", value)
    judge_run.argv += ["--judge-api-key-env", "TEST_JUDGE_KEY"]
    assert judge_run.judge.main() == 2
    judge_run.client.assert_not_called()
    judge_run.load.assert_not_called()
    stderr = capsys.readouterr().err
    assert "TEST_JUDGE_KEY" in stderr and "환경변수가 없거나 빈 값" in stderr
    assert "synthetic-fallback-key" not in stderr


@pytest.mark.parametrize("value", [None, "", "synthetic-env-key"])
def test_explicit_key_wins_even_if_named_environment_is_invalid(judge_run, monkeypatch, value):
    if value is not None:
        monkeypatch.setenv("TEST_JUDGE_KEY", value)
    judge_run.argv += ["--judge-api-key-env", "TEST_JUDGE_KEY", "--judge-api-key", "synthetic-direct-key"]
    assert judge_run.judge.main() == 10
    judge_run.client.assert_called_once_with("https://unused.invalid/v1", "synthetic-direct-key")


def test_no_key_options_keep_existing_client_fallback(judge_run):
    assert judge_run.judge.main() == 10
    judge_run.client.assert_called_once_with("https://unused.invalid/v1", None)
