"""무엇: JSONL 읽기·추가·복구 · 입력: 기존 fixture/손상 줄 · 출력: 왕복·거부·fsync · 계약 §5-5b."""

import json
import os
from pathlib import Path

import pytest

from jeveval.io.records import append_record, read_attempts, read_finals, record_line, repair_tail
from jeveval.types import AttemptRecord, FinalRecord, ParsedAnswer


ROOT = Path(__file__).parents[1] / "fixtures"


def fixture(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def attempt(**changes):
    source = fixture("resume/broken_last_line.json")["expected"]["kept_attempts"][0]
    return AttemptRecord.from_dict(dict(source, **changes))


@pytest.mark.parametrize("name", ["broken_last_line", "broken_middle_line"])
def test_existing_broken_fixtures(tmp_path, name):
    source = fixture(f"resume/{name}.json")
    path = tmp_path / "attempts"
    raw = source["attempts_jsonl"].encode()
    path.write_bytes(raw)
    if source["expected"]["refuse"]:
        with pytest.raises(ValueError, match="line 2"):
            read_attempts(path)
    else:
        records, warnings = read_attempts(path)
        assert [r.to_dict() for r in records] == source["expected"]["kept_attempts"]
        assert warnings == ["truncated_last_line"]
    assert path.read_bytes() == raw


@pytest.mark.parametrize("name", ["duplicate_id", "completed_id"])
def test_existing_final_fixtures(tmp_path, name):
    source = fixture(f"resume/{name}.json")
    path = tmp_path / "final"
    path.write_text(source["final_jsonl"], encoding="utf-8")
    if name == "duplicate_id":
        with pytest.raises(ValueError, match="line 2"):
            read_finals(path)
    else:
        records, warnings = read_finals(path)
        assert [r.logical_id for r in records] == source["expected"]["skip_logical_ids"]
        assert warnings == []


def test_roundtrip_fixture_append_read_and_flush_fsync(tmp_path, monkeypatch):
    path, calls = tmp_path / "final", []
    records = [FinalRecord.from_dict(c["record"]) for c in fixture("records/roundtrip.json")["cases"]]
    fsync = os.fsync

    def check_flush(fd):
        calls.append(fd)
        assert path.read_bytes() == b"".join(record_line(r) for r in records[:len(calls)])
        fsync(fd)

    monkeypatch.setattr(os, "fsync", check_flush)
    for record in records:
        append_record(path, record)
    restored, warnings = read_finals(path)
    assert (restored, warnings) == (records, []) and len(calls) == len(records)
    assert isinstance(restored[0].calls[0].answers_parsed["ready"], ParsedAnswer)


@pytest.mark.parametrize("tail,warning", [(b'{"call_id":', "truncated_last_line"),
    (b'{"x":"\xed\x95', "truncated_last_line"), (b"", "missing_final_newline")])
def test_repair_append_read_integration(tmp_path, monkeypatch, tail, warning):
    path = tmp_path / "attempts"
    original = record_line(attempt()) + tail if tail else record_line(attempt()).rstrip(b"\n")
    path.write_bytes(original)
    assert read_attempts(path) == ([attempt()], [warning])
    assert path.read_bytes() == original
    syncs, fsync = [], os.fsync
    monkeypatch.setattr(os, "fsync", lambda fd: (syncs.append(fd), fsync(fd)))
    assert repair_tail(path) == [warning] and len(syncs) == 1
    assert path.read_bytes() == record_line(attempt())
    assert repair_tail(path) == [] and len(syncs) == 1
    append_record(path, attempt(attempt=2))
    assert read_attempts(path) == ([attempt(), attempt(attempt=2)], [])
    assert len(syncs) == 2


@pytest.mark.parametrize("rows", [[attempt(), attempt()], [attempt(attempt=2)],
    [attempt(), attempt(attempt=3)], [attempt(terminal=True), attempt(attempt=2)],
    [attempt(terminal=True), attempt(attempt=2, terminal=True)],
    [attempt(), attempt(attempt=2, logical_id="changed")],
    [attempt(), attempt(attempt=2, request_sha256="b" * 64)]])
def test_attempt_invariants(tmp_path, rows):
    path = tmp_path / "attempts"
    path.write_bytes(b"".join(record_line(r) for r in rows))
    with pytest.raises(ValueError, match="line [12]"):
        read_attempts(path)


@pytest.mark.parametrize("data", [{}, [], {**attempt().to_dict(), "attempt": "1"},
    {**attempt().to_dict(), "terminal": None}, {**attempt().to_dict(), "unknown": 1}])
@pytest.mark.parametrize("last", [True, False])
def test_type_errors_are_never_discarded(tmp_path, data, last):
    path = tmp_path / "attempts"
    raw = record_line(attempt()) + json.dumps(data).encode()
    path.write_bytes(raw if last else raw + b"\n" + record_line(attempt(attempt=2)))
    with pytest.raises(ValueError, match="line 2: invalid record"):
        read_attempts(path)


def test_interleaved_calls_legacy_retry_after_and_executor_budget(tmp_path):
    path = tmp_path / "attempts"
    rows = [attempt(), attempt(call_id="other", retry_after=1.0),
            *[attempt(attempt=i) for i in range(2, 7)]]
    path.write_bytes(b"".join(record_line(row) for row in rows))
    assert read_attempts(path) == (rows, [])


def test_missing_empty_files_and_missing_parent(tmp_path):
    path = tmp_path / "absent"
    assert read_attempts(path) == read_finals(path) == ([], [])
    assert repair_tail(path) == [] and not path.exists()
    with pytest.raises(FileNotFoundError):
        append_record(tmp_path / "absent_parent/file", attempt())
    path.write_bytes(b"")
    assert read_attempts(path) == read_finals(path) == ([], []) and repair_tail(path) == []


def test_repair_refuses_middle_damage_without_mutation(tmp_path):
    path = tmp_path / "attempts"
    raw = fixture("resume/broken_middle_line.json")["attempts_jsonl"].encode()
    path.write_bytes(raw)
    with pytest.raises(ValueError, match="line 2"):
        repair_tail(path)
    assert path.read_bytes() == raw


def test_record_bytes_and_only_broken_line_repair(tmp_path):
    record = attempt(response_raw="한글\n본문")
    expected = (json.dumps(record.to_dict(), ensure_ascii=False, separators=(",", ":")) + "\n").encode()
    assert record_line(record) == expected
    path = tmp_path / "attempts"
    path.write_bytes(b"broken\n")
    assert repair_tail(path) == ["truncated_last_line"] and path.read_bytes() == b""
    append_record(path, record)
    assert read_attempts(path) == ([record], [])
