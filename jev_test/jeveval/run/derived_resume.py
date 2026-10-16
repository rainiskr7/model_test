"""무엇: 파생 판 재개 판정 · 입력: 실행 폴더·단계·만든 final·출처 · 출력: 이어 쓸 위치(기존 수) · 계약 §8-6 K (상태기계 모듈군)."""

from jeveval.io import derived_stage, records


def check_derived_resume(stage, finals, derived_from, files, *, allow_tail=False) -> int:
    """읽어 둔 기록(io/derived_stage.read_derived_stage)으로 재개 가능 여부를 정한다. gate 이전에는 복구 가능한 tail 을 허용한다."""
    if stage not in derived_stage.STAGES:
        raise ValueError("invalid stage")
    if not isinstance(derived_from, str) or not derived_from:
        raise ValueError("derived_from is required")
    ids = [f.logical_id for f in finals]
    if len(set(ids)) != len(ids) or any(f.derived_from != derived_from for f in finals):
        raise ValueError("inconsistent derived finals")
    for final in finals:
        records.record_line(final)
    if ((not allow_tail and (files.warnings or files.pending)) or files.attempts
            or files.existing != finals[:len(files.existing)]):
        raise ValueError("derived stage records mismatch or need repair")
    if files.provenance is not None and files.provenance != {"derived_from": derived_from}:
        raise ValueError("derived source mismatch")
    return len(files.existing)


def resume_derived(run_dir, stage, finals, derived_from, *, allow_tail=False) -> int:
    """읽기(io) + 판정(run)을 묶는다. 반환값은 write_derived_stage 의 existing_count."""
    files = derived_stage.read_derived_stage(run_dir, stage)
    return check_derived_resume(stage, finals, derived_from, files, allow_tail=allow_tail)
