"""Pin JSON bytes, cleanup, and the four standalone consumers' shared writer."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest


SHARED = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SHARED))
from jsonwrite.atomic_json import write_json_atomic


def test_written_bytes_match_json_dumps_with_final_lf(tmp_path):
    data = {"한글": "서울", "ordered": [1, None, True], "nested": {"z": 2, "a": 1}}
    path = tmp_path / "summary.json"
    write_json_atomic(path, data)
    assert path.read_bytes() == (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def test_parent_directories_are_created(tmp_path):
    path = tmp_path / "new" / "nested" / "summary.json"
    write_json_atomic(path, {"value": 1})
    assert path.is_file()


def test_serialization_failure_leaves_no_target_or_temporary_file(tmp_path):
    path = tmp_path / "summary.json"
    with pytest.raises(TypeError):
        write_json_atomic(path, {"unsupported": {1, 2}})
    assert not path.exists()
    assert list(tmp_path.iterdir()) == []


def test_replace_failure_preserves_existing_bytes_and_removes_temporary_file(monkeypatch, tmp_path):
    from jsonwrite import atomic_json

    path = tmp_path / "summary.json"
    original = b'{"existing": "bytes stay unchanged"}\n'
    path.write_bytes(original)
    failure = OSError("synthetic replace failure")
    replacements = []

    def fail_replace(source, destination):
        replacements.append((source, destination))
        assert Path(source).is_file()
        assert destination == path
        raise failure

    monkeypatch.setattr(atomic_json.os, "replace", fail_replace)
    with pytest.raises(OSError) as caught:
        write_json_atomic(path, {"새 값": "서울"})
    assert caught.value is failure
    assert len(replacements) == 1
    assert path.read_bytes() == original
    assert list(tmp_path.iterdir()) == [path]


def test_all_four_consumers_import_the_same_writer():
    paths = (
        "functionchat/runner/run_functionchat.py",
        "functionchat/scoring/score_run.py",
        "taubench/runner/run_taubench.py",
        "taubench/scoring/score_run.py",
    )
    previous_path = sys.path[:]
    try:
        for index, path in enumerate(paths):
            spec = importlib.util.spec_from_file_location(f"atomic_consumer_{index}", SHARED / path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            assert module.write_json_atomic is write_json_atomic, path
    finally:
        sys.path[:] = previous_path
