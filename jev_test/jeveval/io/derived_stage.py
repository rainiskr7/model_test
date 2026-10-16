"""무엇: 파생 판 단계 기록 · 입력: 실행 폴더·final·출처 · 출력: derived.json·final.jsonl 쓰기/재개 검사 · 계약 §8-6 K."""

from pathlib import Path

from jeveval.io import records
from jeveval.io.run_files import exists, read_json, write_json


def check_derived_stage(run_dir, stage, finals, derived_from, *, allow_tail=False):
    """파생 재개를 읽기만으로 검사한다. gate 이전에는 복구 가능한 tail을 허용한다."""
    if stage not in ("dev", "test", "extra"):
        raise ValueError("invalid stage")
    if not isinstance(derived_from, str) or not derived_from:
        raise ValueError("derived_from is required")
    root = Path(run_dir) / stage
    final_path, attempt_path, marker = root / "final.jsonl", root / "attempts.jsonl", root / "derived.json"
    provenance = {"derived_from": derived_from}
    ids = [f.logical_id for f in finals]
    if len(set(ids)) != len(ids) or any(f.derived_from != derived_from for f in finals):
        raise ValueError("inconsistent derived finals")
    for final in finals:
        records.record_line(final)
    existing, warnings = records.read_finals(final_path)
    attempts, pending = records.read_attempts(attempt_path)
    if ((not allow_tail and (warnings or pending)) or attempts
            or existing != finals[:len(existing)]):
        raise ValueError("derived stage records mismatch or need repair")
    if exists(marker) and read_json(marker) != provenance:
        raise ValueError("derived source mismatch")
    return existing


def write_derived_stage(run_dir, stage, finals, derived_from):
    """gate 통과 뒤 출처를 먼저 쓰고 final을 이어 쓴다. 동일 완료/접두 기록 재개는 멱등이다."""
    existing = check_derived_stage(run_dir, stage, finals, derived_from)
    root = Path(run_dir) / stage
    final_path, attempt_path, marker = root / "final.jsonl", root / "attempts.jsonl", root / "derived.json"
    provenance = {"derived_from": derived_from}
    records.ensure_file(attempt_path)
    records.ensure_file(final_path)
    if not exists(marker):
        write_json(marker, provenance)
    for final in finals[len(existing):]:
        records.append_record(final_path, final)
