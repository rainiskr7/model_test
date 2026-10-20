"""입력: 합성 YAML·격리 import. 출력: 선언 구조·경로·중복·CLI 파일 보존 검증."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from reports.report_multimodal_tracks import main
from shared.multimodal.rescore.report_inputs import ConfigError, read_yaml, validate_conditions, validate_pairs
from shared.multimodal.tests.test_rescore_report_inputs_units import circular_session


@pytest.mark.parametrize("value", [
    None, {}, [{"a": "a", "b": "b"}], [{"a": "a", "b": "b", "bench": "unknown"}],
    [{"a": "a", "b": "b", "bench": []}], [{"a": "a", "b": "a", "bench": "k_mmbench"}],
    [{"a": "a", "b": "b", "bench": "k_mmbench", "extra": 1}],
])
def test_pair_structure_and_bench_validation(value):
    with pytest.raises(ConfigError):
        validate_pairs(value)


@pytest.mark.parametrize("name", ["", ".", "..", "a/../b", "/absolute", "a\\b", "../x", "a..b", None, 1])
def test_pair_paths_are_single_directory_names(name):
    with pytest.raises(ConfigError):
        validate_pairs([{"a": name, "b": "b", "bench": "k_dtcbench"}])


def test_pair_duplicates_including_reverse_direction():
    first = {"a": "a", "b": "b", "bench": "mtvqa_kr"}
    for second in (first, {**first, "a": "b", "b": "a"}):
        with pytest.raises(ConfigError, match="duplicate"):
            validate_pairs([first, second])
    assert validate_pairs([]) == []
    assert len(validate_pairs([first, {**first, "bench": "k_mmbench"}])) == 2


@pytest.mark.parametrize("change", [
    {"model": ""}, {"model": None}, {"evidence": ""}, {"evidence": 1},
    {"sessions": []}, {"sessions": "r1"}, {"sessions": ["../r1"]},
    {"sessions": ["r1", "r1"]}, {"generation_config": "unknown"}, {"extra": True},
])
def test_serving_declaration_schema_scope_and_duplicates(change):
    row = {"model": "org/model", "sessions": ["r1"], "generation_config": "vllm", "evidence": "record"}
    with pytest.raises(ConfigError):
        validate_conditions([{**row, **change}])
    with pytest.raises(ConfigError):
        validate_conditions([row, row])
    assert validate_conditions([row]) == [row]
    assert validate_conditions([]) == []


@pytest.mark.parametrize("value", [None, {}, [{}]])
def test_serving_invalid_root_or_missing_keys(value):
    with pytest.raises(ConfigError):
        validate_conditions(value)


def test_yaml_io_missing_optional_and_safe_parse_failure(tmp_path):
    path = tmp_path / "missing.yaml"
    assert read_yaml(path, optional=True) == []
    with pytest.raises(ConfigError):
        read_yaml(path)
    path.write_text("SECRET_SENTINEL: [")
    with pytest.raises(ConfigError) as error:
        read_yaml(path)
    assert "SECRET_SENTINEL" not in str(error.value)
    path.write_text("[]")
    assert read_yaml(path) == []


@pytest.mark.parametrize("payload", ["SECRET_SENTINEL: [", "{}", "[{}]", '[{"model":"a"}]'])
def test_actual_bad_yaml_cli_rc2_preserves_output_and_no_official_bypasses(tmp_path, capsys, payload):
    circular_session(tmp_path)
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs/serving_conditions.yaml").write_text(payload)
    output = tmp_path / "report.md"
    output.write_text("preserve")
    args = ["--base", str(tmp_path), "--write-markdown", str(output)]
    assert main(args) == 2
    assert output.read_text() == "preserve"
    assert "SECRET_SENTINEL" not in capsys.readouterr().err
    assert main(args + ["--no-official"]) == 0
    assert "참고 지표 — 공식 방식 재채점" not in output.read_text()


def test_import_does_not_read_yaml_write_or_change_environment(tmp_path):
    root = Path(__file__).resolve().parents[3]
    code = """
import importlib, os, sys
before = dict(os.environ)
def audit(event, args):
    if event == 'open':
        if isinstance(args[0], str) and args[0].endswith('.yaml'):
            raise AssertionError('YAML read at import')
        if isinstance(args[2], int) and args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT):
            raise AssertionError('write at import')
    if event.startswith('socket.'):
        raise AssertionError('network')
sys.addaudithook(audit)
for module in ('report_inputs', 'report_section', 'conditions_section'):
    importlib.import_module('shared.multimodal.rescore.' + module)
importlib.import_module('shared.stats.report_pairs')
importlib.import_module('reports.report_multimodal_tracks')
assert dict(os.environ) == before
"""
    outcome = subprocess.run([sys.executable, "-B", "-c", code], cwd=tmp_path, capture_output=True,
                             env={**os.environ, "PYTHONPATH": str(root), "PYTHONDONTWRITEBYTECODE": "1"})
    assert outcome.returncode == 0, outcome.stderr.decode()
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("pair", [
    {"a": "../escape", "b": "b", "bench": "k_mmbench"},
    {"a": "a", "b": "b", "bench": "unknown"}, {"a": "a"},
])
def test_bad_pair_yaml_cli_preserves_output(tmp_path, monkeypatch, capsys, pair):
    circular_session(tmp_path)
    pairfile = tmp_path / "bad-pairs.yaml"
    pairfile.write_text(json.dumps([pair]))
    monkeypatch.setattr("shared.multimodal.rescore.report_inputs.read_yaml",
                        lambda path, optional=False: [] if optional else read_yaml(pairfile))
    output = tmp_path / "report.md"
    output.write_text("preserve")
    assert main(["--base", str(tmp_path), "--write-markdown", str(output)]) == 2
    assert output.read_text() == "preserve"
    assert "report configuration rejected" in capsys.readouterr().err
