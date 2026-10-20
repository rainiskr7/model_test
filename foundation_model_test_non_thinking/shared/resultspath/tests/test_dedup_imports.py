"""Step 7 aliases and scorer defaults remain part of their original modules."""

from importlib import import_module
from pathlib import Path

import pytest

from shared.jsonread.object import load_json_object
from shared.reproidentity.core import digest, metadata_identity
from shared.resultspath.model_dir import results_model_dir_name, safe_model_name


@pytest.mark.parametrize("module_name,name,expected", [
    ("shared.agent.scoring.aggregate", "safe_model_name", safe_model_name),
    ("shared.agent.scoring.aggregate", "results_model_dir_name", results_model_dir_name),
    ("shared.agent.scoring.score_run", "safe_model_name", safe_model_name),
    ("shared.agent.scoring.score_run", "results_model_dir_name", results_model_dir_name),
    ("shared.agent.scoring.validate_run", "safe_model_name", safe_model_name),
    ("shared.agent.scoring.validate_run", "results_model_dir_name", results_model_dir_name),
    ("shared.functionchat.scoring.score_run", "safe_model_name", safe_model_name),
    ("shared.functionchat.scoring.score_run", "results_model_dir_name", results_model_dir_name),
    ("shared.functionchat.scoring.score_run", "_load", load_json_object),
    ("shared.functionchat.runner.run_functionchat", "_safe_model_name", safe_model_name),
    ("shared.functionchat.runner.run_functionchat", "_results_model_dir_name", results_model_dir_name),
    ("shared.multimodal.benches.paths", "safe_model_name", safe_model_name),
    ("shared.multimodal.benches.paths", "results_model_dir_name", results_model_dir_name),
    ("shared.nlu.nlu_gpustack", "safe_model_name", safe_model_name),
    ("shared.nlu.nlu_gpustack", "results_model_dir_name", results_model_dir_name),
    ("shared.taubench.runner.run_taubench", "safe_model_name", safe_model_name),
    ("shared.taubench.runner.run_taubench", "results_model_dir_name", results_model_dir_name),
    ("shared.taubench.scoring.score_run", "safe_model_name", safe_model_name),
    ("shared.taubench.scoring.score_run", "results_model_dir_name", results_model_dir_name),
    ("shared.taubench.scoring.score_run", "_load", load_json_object),
    ("shared.agent.scoring.repro", "_digest", digest),
    ("shared.agent.scoring.repro", "_identity", metadata_identity),
    ("shared.functionchat.scoring.repro", "_digest", digest),
    ("shared.functionchat.scoring.repro", "_metadata_identity", metadata_identity),
])
def test_original_module_attribute_is_shared_function(module_name, name, expected):
    assert getattr(import_module(module_name), name) is expected


@pytest.mark.parametrize("track", ["functionchat", "taubench"])
def test_scorer_default_root_is_non_thinking_without_environment(monkeypatch, track):
    monkeypatch.delenv("MODEL_TEST_BASE", raising=False)
    monkeypatch.delenv("EVAL_TIMESTAMP", raising=False)
    # No real results directory is needed or inspected by this default-root test.
    monkeypatch.setattr(Path, "is_dir", lambda path: False)
    module = import_module(f"shared.{track}.scoring.score_run")
    args = module.parse_args(["--model", "fixture/model", "--timestamp", "session"])
    root = Path(__file__).resolve().parents[3]
    assert module._results_dir(args) == root / "results/fixture_model/session/language" / track
