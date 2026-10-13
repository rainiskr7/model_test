"""무엇: 실행 JSON 정규 바이트·원자 교체 · 입력: 경로·객체 · 출력: 파일/객체 · 계약 §8-6 F·M."""

import json
import os
from pathlib import Path
import tempfile

from jeveval.io.hashes import sha256_file as file_sha256
from jeveval.types import JsonRecord


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
