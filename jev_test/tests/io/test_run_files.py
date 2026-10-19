"""무엇: 실행 JSON 입출력 경계 · 입력: 합성 객체·임시 경로 · 출력: 바이트·복원 · 계약 §8-6 M."""

import hashlib

import pytest

from jeveval.io import run_files
from jeveval.types import Decision


def test_canonical_bytes_and_roundtrip(tmp_path):
    expected = '{\n "a": "한글",\n "z": 1\n}\n'.encode("utf-8")
    assert run_files.json_bytes({"z": 1, "a": "한글"}) == expected
    path = tmp_path / "result.json"
    run_files.write_json(path, {"z": 1, "a": "한글"})
    assert path.read_bytes() == expected
    assert run_files.file_sha256(path) == hashlib.sha256(expected).hexdigest()
    assert run_files.read_json(path) == {"a": "한글", "z": 1}
    value = Decision(False, 2.0)
    run_files.write_json(path, value)
    assert run_files.read_json(path, Decision) == value


def test_fsync_before_atomic_replace(tmp_path, monkeypatch):
    path = tmp_path / "result.json"
    path.write_bytes(b"original")
    events = []
    fsync, replace = run_files.os.fsync, run_files.os.replace

    def sync(fd):
        assert path.read_bytes() == b"original"
        events.append("fsync")
        fsync(fd)

    def swap(source, destination):
        assert source.parent == path.parent
        assert source.read_bytes() == run_files.json_bytes({"new": True})
        assert path.read_bytes() == b"original" and events == ["fsync"]
        events.append("replace")
        replace(source, destination)

    monkeypatch.setattr(run_files.os, "fsync", sync)
    monkeypatch.setattr(run_files.os, "replace", swap)
    run_files.write_json(path, {"new": True})
    assert events == ["fsync", "replace"] and list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize("step", ["fsync", "replace"])
def test_failed_write_keeps_original_and_cleans_temp(tmp_path, monkeypatch, step):
    path = tmp_path / "result.json"
    path.write_bytes(b"original")

    def fail(*args):
        raise OSError("synthetic failure")

    monkeypatch.setattr(run_files.os, step, fail)
    with pytest.raises(OSError):
        run_files.write_json(path, {"new": True})
    assert path.read_bytes() == b"original" and list(tmp_path.iterdir()) == [path]


def test_no_parent_creation(tmp_path):
    with pytest.raises(FileNotFoundError):
        run_files.write_json(tmp_path / "missing" / "result.json", {})
    assert not (tmp_path / "missing").exists()


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_write_rejected_without_change(tmp_path, value):
    path = tmp_path / "result.json"
    path.write_bytes(b"original")
    with pytest.raises(ValueError):
        run_files.write_json(path, {"value": value})
    assert path.read_bytes() == b"original" and list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize("body", ['{"a":1,"a":2}', '{"a":{"x":1,"x":2}}',
                                  '{"a":NaN}', '{"a":Infinity}', '{"a":-Infinity}', '{"a":1e999}'])
def test_invalid_json_read(tmp_path, body):
    path = tmp_path / "result.json"
    path.write_text(body)
    with pytest.raises(ValueError):
        run_files.read_json(path)


def test_copy_preserves_bytes_and_fsync_order(tmp_path, monkeypatch):
    src, dst = tmp_path / "source", tmp_path / "target"
    payload = b"\xff\x00 \r\n{\"unsorted\":  1}\n"
    src.write_bytes(payload)
    dst.write_bytes(b"old")
    events, sync, swap = [], run_files.os.fsync, run_files.os.replace
    def fsync(fd):
        assert dst.read_bytes() == b"old"
        events.append("fsync")
        sync(fd)
    def replace(source, destination):
        assert source.parent == dst.parent and source.read_bytes() == payload
        assert events == ["fsync"] and dst.read_bytes() == b"old"
        events.append("replace")
        swap(source, destination)
    monkeypatch.setattr(run_files.os, "fsync", fsync)
    monkeypatch.setattr(run_files.os, "replace", replace)
    run_files.copy_bytes(src, dst)
    assert run_files.read_bytes(dst) == run_files.read_bytes(src) == payload
    assert events == ["fsync", "replace"]


@pytest.mark.parametrize("step", ["fsync", "replace", "parent", "source"])
def test_copy_failure_preserves_files(tmp_path, monkeypatch, step):
    src, dst = tmp_path / "source", tmp_path / "target"
    src.write_bytes(b"new")
    dst.write_bytes(b"old")
    if step in ("fsync", "replace"):
        def fail(*args):
            raise OSError("synthetic")
        monkeypatch.setattr(run_files.os, step, fail)
    with pytest.raises(OSError):
        run_files.copy_bytes(tmp_path / "absent" if step == "source" else src,
                             tmp_path / "missing/target" if step == "parent" else dst)
    assert src.read_bytes() == b"new" and dst.read_bytes() == b"old"
    assert set(tmp_path.iterdir()) == {src, dst}


def test_write_text_atomic_utf8_and_non_string_rejected(tmp_path, monkeypatch):
    path = tmp_path / "report.md"
    path.write_text("before")
    original = run_files.os.replace
    def replace(source, destination):
        assert path.read_text() == "before" and source.read_bytes() == "한글\n".encode()
        original(source, destination)
    monkeypatch.setattr(run_files.os, "replace", replace)
    run_files.write_text(path, "한글\n")
    assert path.read_text() == "한글\n"
    with pytest.raises(TypeError):
        run_files.write_text(path, {})
