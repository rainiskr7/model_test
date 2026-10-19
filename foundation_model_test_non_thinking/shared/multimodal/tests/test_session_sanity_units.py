"""9-1a sanity output order and module patch reach, with synthetic inputs."""

import builtins
import sys
from pathlib import Path
from types import ModuleType

import pytest

from shared.multimodal.benches import session_sanity as sanity


@pytest.fixture
def schema(monkeypatch):
    module = ModuleType("_schema")
    module.detect_and_validate = lambda *args: ("synthetic", None)
    module.diagnostic_warnings = lambda *args: []
    module.publish_status_error = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "_schema", module)
    monkeypatch.setattr(sys, "path", sys.path.copy())
    return module


def test_main_patches_reach_file_checks_and_warnings_precede_failures(tmp_path, monkeypatch, capsys, schema):
    paths = [tmp_path / "vision/one.json", tmp_path / "vision/two.json"]
    calls = []
    monkeypatch.setattr(sanity, "iter_result_files", lambda session: iter(paths))

    def check(path, rel, model, selected_schema):
        calls.append((path, rel, model, selected_schema))
        return [f"  failure {rel}"], [f"  warning {rel}"]

    monkeypatch.setattr(sanity, "check_file", check)
    assert sanity.main([str(tmp_path), "model", "synthetic-benches"]) == 1
    assert capsys.readouterr() == (
        "[sanity] 2 건의 비치명 경고:\n  warning vision/one.json\n  warning vision/two.json\n"
        "[sanity] 2 건의 실패 결과:\n  failure vision/one.json\n  failure vision/two.json\n", "",
    )
    assert calls == [(path, Path(rel), "model", (
        schema.detect_and_validate, schema.diagnostic_warnings, schema.publish_status_error,
    )) for path, rel in zip(paths, ("vision/one.json", "vision/two.json"))]
    assert sys.path[0] == "synthetic-benches"


def test_absent_session_still_loads_schema_and_returns_zero(tmp_path, monkeypatch, capsys, schema):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sanity, "iter_result_files", lambda session: pytest.fail("scanned absent session"))
    assert sanity.main(["absent", "model", "synthetic-benches"]) == 0
    assert sys.path[0] == "synthetic-benches"
    assert capsys.readouterr() == ("[sanity] WARN: session dir 없음 absent\n", "")


def test_load_schema_import_exception_keeps_legacy_fallback(monkeypatch, capsys):
    original_import = builtins.__import__
    monkeypatch.setattr(sys, "path", sys.path.copy())

    def failing_import(name, *args, **kwargs):
        if name == "_schema":
            raise ValueError("synthetic schema error")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", failing_import)
    assert sanity._load_schema(Path("synthetic-benches")) is None
    assert sys.path[0] == "synthetic-benches"
    assert capsys.readouterr() == (
        "[sanity] schema module 로드 실패 (synthetic schema error) — legacy 키 검사만\n", "",
    )


@pytest.mark.parametrize("warnings,expected", [
    ([], "[sanity] OK — 치명적 결과 없음\n"),
    (["  warning"], "[sanity] 1 건의 비치명 경고:\n  warning\n[sanity] OK — 치명적 결과 없음\n"),
])
def test_print_results_warnings_do_not_change_success_rc(capsys, warnings, expected):
    assert sanity._print_results([], warnings) == 0
    assert capsys.readouterr() == (expected, "")
