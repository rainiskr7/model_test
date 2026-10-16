"""무엇: 파생 재개 판정 · 입력: 기록 묶음·현재 final · 출력: 거부/이어 쓸 수 · 계약 §8-6 K."""

from dataclasses import replace
import re

import pytest

from jeveval.io import derived_stage, records, run_files
from jeveval.run.derived_resume import check_derived_resume, resume_derived
from jeveval.run.gate import prepare_stage
from jeveval.types import DerivedStageFiles, FinalRecord
from tests.run.stage_support import plan_for, snapshot
from tests.types.samples import attempt


def derived(logical_id="synthetic:g:ok"):
    return FinalRecord(logical_id, "error", "request_contract", False, [], [], "full/run")


@pytest.fixture
def files():
    return DerivedStageFiles([], [], [], [], None)


@pytest.mark.parametrize("case,message", [
    ("stage", "invalid stage"), ("source_missing", "derived_from is required"),
    ("source_empty", "derived_from is required"), ("source_type", "derived_from is required"),
    ("duplicate", "inconsistent derived finals"), ("final_source", "inconsistent derived finals"),
    ("attempt", "derived stage records mismatch or need repair"),
    ("prefix", "derived stage records mismatch or need repair"),
    ("longer", "derived stage records mismatch or need repair"),
    ("marker", "derived source mismatch"), ("empty_marker", "derived source mismatch")])
def test_rejects_invalid_resume_inputs(files, case, message):
    stage, finals, source = "dev", [derived()], "full/run"
    if case == "stage":
        stage = "../bad"
    elif case.startswith("source_"):
        source = {"source_missing": None, "source_empty": "", "source_type": 1}[case]
    elif case == "duplicate":
        finals *= 2
    elif case == "final_source":
        finals = [replace(finals[0], derived_from="other")]
    elif case == "attempt":
        files = replace(files, attempts=[attempt()])
    elif case == "prefix":
        files = replace(files, existing=[derived("synthetic:g:changed")])
    elif case == "longer":
        files = replace(files, existing=finals + [derived("synthetic:g:second")])
    else:
        files = replace(files, provenance={} if case == "empty_marker" else {"derived_from": "other"})
    before = (list(finals), files)
    with pytest.raises(ValueError, match="^" + re.escape(message) + "$"):
        check_derived_resume(stage, finals, source, files, allow_tail=True)
    assert (finals, files) == before


@pytest.mark.parametrize("field", ["warnings", "pending"])
def test_allow_tail_only_relaxes_repair_warnings(files, field):
    finals = [derived()]
    files = replace(files, existing=finals, **{field: ["truncated_last_line"]})
    with pytest.raises(ValueError, match="^derived stage records mismatch or need repair$"):
        check_derived_resume("dev", finals, "full/run", files)
    assert check_derived_resume("dev", finals, "full/run", files, allow_tail=True) == 1
    with pytest.raises(ValueError, match="^derived stage records mismatch or need repair$"):
        check_derived_resume("dev", finals, "full/run", replace(files, attempts=[attempt()]), allow_tail=True)


@pytest.mark.parametrize("stage", ["dev", "test", "extra"])
@pytest.mark.parametrize("existing_count", [0, 1, 2])
def test_returns_existing_prefix_count(files, stage, existing_count):
    finals = [derived(), derived("synthetic:g:second")]
    files = replace(files, existing=finals[:existing_count], provenance={"derived_from": "full/run"})
    assert check_derived_resume(stage, finals, "full/run", files) == existing_count


def test_empty_stage_is_resumable(files):
    assert check_derived_resume("dev", [], "full/run", files) == 0


def test_unserializable_final_is_rejected(files):
    with pytest.raises(TypeError):
        check_derived_resume("dev", [replace(derived(), warnings=[object()])], "full/run", files)


def test_resume_reads_without_repair_or_writes(tmp_path):
    finals = [derived(), derived("synthetic:g:second")]
    assert resume_derived(tmp_path, "dev", finals, "full/run") == 0
    assert snapshot(tmp_path) == {}
    (tmp_path / "dev").mkdir()
    (tmp_path / "dev/final.jsonl").write_bytes(records.record_line(finals[0]) + b'{"broken":')
    before = snapshot(tmp_path)
    with pytest.raises(ValueError, match="^derived stage records mismatch or need repair$"):
        resume_derived(tmp_path, "dev", finals, "full/run")
    assert resume_derived(tmp_path, "dev", finals, "full/run", allow_tail=True) == 1
    assert snapshot(tmp_path) == before


def test_empty_derived_dev_can_be_sealed(tmp_path):
    """기존 I/O 짝의 빈 dev→test gate 경계 시험을 상태기계 짝으로 이동한다."""
    plan = replace(plan_for(), dev=[])
    prepare_stage(run_dir=tmp_path, stage="dev", fingerprint={}, plan=plan, now="now")
    existing = resume_derived(tmp_path, "dev", [], "full/run")
    derived_stage.write_derived_stage(tmp_path, "dev", [], "full/run", existing)
    run_files.write_json(tmp_path / "threshold.json", {})
    prepare_stage(run_dir=tmp_path, stage="test", fingerprint={}, plan=plan, now="now")
    assert run_files.read_json(tmp_path / "test/seal.json")["dev_final_sha256"] == (
        run_files.file_sha256(tmp_path / "dev/final.jsonl"))
