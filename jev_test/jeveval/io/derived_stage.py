"""무엇: 파생 판 단계 기록 읽기/쓰기 · 입력: 실행 폴더·final·출처 · 출력: 기존 기록 묶음 / derived.json·final.jsonl 쓰기 · 계약 §8-6 K."""

from pathlib import Path

from jeveval.io import records
from jeveval.io.run_files import exists, read_json, write_json
from jeveval.types import DerivedStageFiles

STAGES = ("dev", "test", "extra")


def _paths(run_dir, stage):
    if stage not in STAGES:
        raise ValueError("invalid stage")
    root = Path(run_dir) / stage
    return root / "final.jsonl", root / "attempts.jsonl", root / "derived.json"


def read_derived_stage(run_dir, stage) -> DerivedStageFiles:
    """읽기만 한다 — 재개 가능 판정은 run/derived_resume."""
    final_path, attempt_path, marker = _paths(run_dir, stage)
    existing, warnings = records.read_finals(final_path)
    attempts, pending = records.read_attempts(attempt_path)
    provenance = read_json(marker) if exists(marker) else None
    return DerivedStageFiles(existing, warnings, attempts, pending, provenance)


def write_derived_stage(run_dir, stage, finals, derived_from, existing_count: int) -> None:
    """gate·재개 판정을 통과한 뒤 출처를 먼저 쓰고 existing_count 뒤의 final 을 이어 쓴다."""
    final_path, attempt_path, marker = _paths(run_dir, stage)
    records.ensure_file(attempt_path)
    records.ensure_file(final_path)
    if not exists(marker):
        write_json(marker, {"derived_from": derived_from})
    for final in finals[existing_count:]:
        records.append_record(final_path, final)
