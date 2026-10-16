"""무엇: 파생 단계 입출력 · 입력: 합성 기록·쓰기 시작 위치 · 출력: 읽은 파일 묶음·바이트 · 계약 §8-6 K."""

import pytest

from jeveval.io import derived_stage, records, run_files
from jeveval.types import DerivedStageFiles, FinalRecord
from tests.run.stage_support import snapshot
from tests.types.samples import attempt


def derived(logical_id="synthetic:g:ok"):
    """비용 관측값 없이도 출처를 가진 최소 파생 기록을 만든다."""
    return FinalRecord(logical_id, "error", "request_contract", False, [], [], "full/run")


def test_ensure_file_preserves_content_and_requires_parent(tmp_path):
    """빈 파일 생성과 fsync 후 재호출은 원래 바이트를 건드리지 않는다."""
    path = tmp_path / "file"
    records.ensure_file(path)
    assert path.read_bytes() == b""
    path.write_bytes(b"existing")
    records.ensure_file(path)
    assert path.read_bytes() == b"existing"
    with pytest.raises(FileNotFoundError):
        records.ensure_file(tmp_path / "missing/file")


@pytest.mark.parametrize("finals", [[], [derived()]])
def test_write_derived_empty_or_populated_idempotent(tmp_path, finals):
    """빈 단계도 cost 출처를 남기며 동일 재호출은 중복 final 없이 바이트를 보존한다."""
    (tmp_path / "dev").mkdir()
    derived_stage.write_derived_stage(tmp_path, "dev", finals, "full/run", 0)
    assert (tmp_path / "dev/attempts.jsonl").read_bytes() == b""
    assert records.read_finals(tmp_path / "dev/final.jsonl")[0] == finals
    assert run_files.read_json(tmp_path / "dev/derived.json") == {"derived_from": "full/run"}
    before = snapshot(tmp_path)
    files = derived_stage.read_derived_stage(tmp_path, "dev")
    assert files == DerivedStageFiles(finals, [], [], [], {"derived_from": "full/run"})
    derived_stage.write_derived_stage(tmp_path, "dev", finals, "full/run", len(files.existing))
    assert snapshot(tmp_path) == before


def test_writer_appends_from_supplied_existing_count(tmp_path, monkeypatch):
    """출처와 첫 final 뒤 중단하면 전달받은 위치 이후만 이어 쓴다."""
    (tmp_path / "dev").mkdir()
    finals = [derived(), derived("synthetic:g:second")]
    append = records.append_record

    def crash(path, row):
        """첫 final을 fsync한 직후 중단한다."""
        append(path, row)
        raise RuntimeError("crash")

    with monkeypatch.context() as patch:
        patch.setattr(records, "append_record", crash)
        with pytest.raises(RuntimeError):
            derived_stage.write_derived_stage(tmp_path, "dev", finals, "full/run", 0)
    assert run_files.read_json(tmp_path / "dev/derived.json")["derived_from"] == "full/run"
    assert records.read_finals(tmp_path / "dev/final.jsonl")[0] == finals[:1]
    derived_stage.write_derived_stage(tmp_path, "dev", finals, "full/run", 1)
    assert records.read_finals(tmp_path / "dev/final.jsonl")[0] == finals


def test_read_derived_stage_preserves_records_warnings_and_provenance(tmp_path):
    """재개 여부를 판단하거나 끝 줄을 복구하지 않고 읽은 다섯 값을 보존한다."""
    (tmp_path / "dev").mkdir()
    final, tried = derived(), attempt()
    (tmp_path / "dev/final.jsonl").write_bytes(records.record_line(final).rstrip(b"\n"))
    (tmp_path / "dev/attempts.jsonl").write_bytes(records.record_line(tried) + b'{"broken":')
    run_files.write_json(tmp_path / "dev/derived.json", {"derived_from": "other"})
    before = snapshot(tmp_path)
    files = derived_stage.read_derived_stage(tmp_path, "dev")
    assert files == DerivedStageFiles([final], ["missing_final_newline"], [tried],
                                     ["truncated_last_line"], {"derived_from": "other"})
    assert snapshot(tmp_path) == before


def test_read_missing_stage_does_not_create_files(tmp_path):
    assert derived_stage.read_derived_stage(tmp_path, "dev") == DerivedStageFiles([], [], [], [], None)
    assert snapshot(tmp_path) == {}


@pytest.mark.parametrize("operation", ["read", "write"])
def test_stage_path_escape_rejected_before_io(tmp_path, operation):
    with pytest.raises(ValueError, match="^invalid stage$"):
        if operation == "read":
            derived_stage.read_derived_stage(tmp_path, "../bad")
        else:
            derived_stage.write_derived_stage(tmp_path, "../bad", [], "full/run", 0)
    assert snapshot(tmp_path) == {}


def test_writer_preserves_existing_marker(tmp_path):
    (tmp_path / "dev").mkdir()
    marker = tmp_path / "dev/derived.json"
    marker.write_text('{ "derived_from": "full/run" }\n')
    before = marker.read_bytes()
    derived_stage.write_derived_stage(tmp_path, "dev", [derived()], "full/run", 0)
    assert marker.read_bytes() == before
