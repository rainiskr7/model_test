"""무엇: 파생 단계 기록 경계 · 입력: 합성 파생 final · 출력: 출처·빈 파일·재개 · 계약 §5-4·⑤d R4."""

from dataclasses import replace

import pytest

from jeveval.io import derived_stage, records, run_files
from jeveval.run.gate import prepare_stage
from jeveval.types import FinalRecord
from tests.run.stage_support import plan_for, snapshot


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
    derived_stage.write_derived_stage(tmp_path, "dev", finals, "full/run")
    assert (tmp_path / "dev/attempts.jsonl").read_bytes() == b""
    assert records.read_finals(tmp_path / "dev/final.jsonl")[0] == finals
    assert run_files.read_json(tmp_path / "dev/derived.json") == {"derived_from": "full/run"}
    before = snapshot(tmp_path)
    derived_stage.write_derived_stage(tmp_path, "dev", finals, "full/run")
    assert snapshot(tmp_path) == before


def test_partial_derived_write_resume(tmp_path, monkeypatch):
    """출처와 첫 final 뒤 중단해도 다음 호출은 남은 final만 이어 쓴다."""
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
            derived_stage.write_derived_stage(tmp_path, "dev", finals, "full/run")
    assert run_files.read_json(tmp_path / "dev/derived.json")["derived_from"] == "full/run"
    derived_stage.write_derived_stage(tmp_path, "dev", finals, "full/run")
    assert records.read_finals(tmp_path / "dev/final.jsonl")[0] == finals


def test_derived_rejects_source_and_record_changes_without_writes(tmp_path):
    """출처/완료 기록 변경·중복·단계 경로 탈출을 쓰기 전에 거부한다."""
    (tmp_path / "dev").mkdir()
    derived_stage.write_derived_stage(tmp_path, "dev", [derived()], "full/run")
    before = snapshot(tmp_path)
    for stage, finals, source in (("dev", [replace(derived(), derived_from="other")], "other"),
                                 ("dev", [derived(), derived()], "full/run"),
                                 ("dev", [], "full/run"), ("../bad", [], "full/run")):
        with pytest.raises(ValueError):
            derived_stage.write_derived_stage(tmp_path, stage, finals, source)
        assert snapshot(tmp_path) == before


def test_empty_derived_dev_can_be_sealed(tmp_path):
    """빈 dev final의 실제 바이트가 있어 다음 test gate가 봉인할 수 있다."""
    plan = replace(plan_for(), dev=[])
    prepare_stage(run_dir=tmp_path, stage="dev", fingerprint={}, plan=plan, now="now")
    derived_stage.write_derived_stage(tmp_path, "dev", [], "full/run")
    run_files.write_json(tmp_path / "threshold.json", {})
    prepare_stage(run_dir=tmp_path, stage="test", fingerprint={}, plan=plan, now="now")
    assert run_files.read_json(tmp_path / "test/seal.json")["dev_final_sha256"] == (
        run_files.file_sha256(tmp_path / "dev/final.jsonl"))
