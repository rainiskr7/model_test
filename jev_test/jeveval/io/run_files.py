"""무엇: 실행 JSON 정규 바이트·원자 교체 · 입력: 경로·객체 · 출력: 파일/객체 · 계약 §8-6 F·M."""

import json
import os
from pathlib import Path
import tempfile

from jeveval.io.hashes import sha256_file as file_sha256
from jeveval.io import records
from jeveval.types import JsonRecord


def exists(path) -> bool:
    """실행 입력/산출물의 존재 여부를 io에서 조회한다."""
    return Path(path).exists()


def make_directory(path) -> None:
    """검사가 끝난 실행기의 출력 폴더를 만든다."""
    Path(path).mkdir(parents=True, exist_ok=True)


def json_bytes(obj) -> bytes:
    """실행 산출물의 UTF-8·정렬 키·한 칸 들여쓰기·끝 LF를 고정한다."""
    data = obj.to_dict() if isinstance(obj, JsonRecord) else obj
    return (json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True,
                       allow_nan=False) + "\n").encode("utf-8")


def write_json(path, obj):
    """같은 폴더의 임시 파일을 fsync한 뒤 교체한다. 부모 폴더는 만들지 않는다."""
    payload, path = json_bytes(obj), Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.",
                                         delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _nonfinite(value):
    raise ValueError("nonfinite JSON number")


def _float(value):
    result = float(value)
    if not -float("inf") < result < float("inf"):
        raise ValueError("nonfinite JSON number")
    return result


def read_json(path, cls=None):
    """중첩 중복 키·비유한 수를 거부하고 선택적으로 JsonRecord를 복원한다."""
    data = json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=_unique,
                      parse_constant=_nonfinite, parse_float=_float)
    return cls.from_dict(data) if cls is not None else data


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
