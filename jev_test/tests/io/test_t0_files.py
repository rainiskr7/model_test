"""T0 JSONL 완전성, 키 순서, 원자 쓰기 경계."""

import json

import pytest

from jeveval.io import t0_files


def test_lines_roundtrip_preserves_insertion_order(tmp_path):
    path = tmp_path / "nested/records.jsonl"
    header, rows = {"schema": "synthetic/1"}, [{"z": "한글", "a": {"B": 2, "A": 1}}]
    t0_files.write_lines(path, header, rows)
    actual_header, actual_rows = t0_files.read_lines(path)
    assert (actual_header, actual_rows) == (header, rows)
    assert list(actual_rows[0]) == ["z", "a"] and list(actual_rows[0]["a"]) == ["B", "A"]
    assert path.read_bytes().endswith(b"\n")


@pytest.mark.parametrize("raw", [b"", b"{}", b"[]\n", b"{}\n[]\n", b'{"x":1,"x":2}\n',
    b'{"x":NaN}\n', b'{"x":1e999}\n', b"{}\n\n", b'{"broken":\n'])
def test_invalid_or_incomplete_lines_rejected(tmp_path, raw):
    path = tmp_path / "records.jsonl"
    path.write_bytes(raw)
    with pytest.raises(ValueError):
        t0_files.read_lines(path)


def test_atomic_replace_failure_preserves_destination_and_cleans_temp(tmp_path, monkeypatch):
    path = tmp_path / "records.jsonl"
    path.write_bytes(b"old")
    events, fsync = [], t0_files.os.fsync
    def synced(fd):
        events.append("fsync")
        return fsync(fd)
    def fail(source, target):
        assert events == ["fsync"] and target == path
        assert source.read_bytes() == b"new"
        raise OSError("synthetic replace failure")
    monkeypatch.setattr(t0_files.os, "fsync", synced)
    monkeypatch.setattr(t0_files.os, "replace", fail)
    with pytest.raises(OSError, match="synthetic replace failure"):
        t0_files.write_bytes(path, b"new")
    assert path.read_bytes() == b"old" and list(tmp_path.iterdir()) == [path]


def test_fixture_writer_preserves_question_and_option_order(tmp_path):
    path = tmp_path / "fixture.json"
    value = dict(schema="t0_fixture/1", seed=42,
        cases=[{"questions": {"z": {"criteria": {"B": "b", "A": "a"}}, "a": {}}}], batches=[])
    t0_files.write_fixture(path, value)
    result = json.loads(path.read_text())
    assert result == value
    assert list(result["cases"][0]["questions"]) == ["z", "a"]
    assert list(result["cases"][0]["questions"]["z"]["criteria"]) == ["B", "A"]
