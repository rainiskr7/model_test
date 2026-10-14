"""무엇: 순서 보존 T0 파일 입출력 · 입력: 단계 객체 · 출력: 원자 JSON/JSONL · 계약 §8-7 T-a/h."""

import json
import os
from pathlib import Path
import tempfile

from jeveval.io.run_files import _unique, _nonfinite, _float
from jeveval.t0.request import canonical_bytes


def write_bytes(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def write_lines(path, header, rows):
    write_bytes(path, b"".join(canonical_bytes(row) + b"\n" for row in [header, *rows]))


def read_lines(path):
    raw = Path(path).read_bytes()
    if not raw.endswith(b"\n"):
        raise ValueError("incomplete T0 file")
    rows = [json.loads(line, object_pairs_hook=_unique, parse_constant=_nonfinite, parse_float=_float)
            for line in raw.splitlines()]
    if not rows or any(not isinstance(row, dict) for row in rows):
        raise ValueError("invalid T0 JSONL")
    return rows[0], rows[1:]


def write_fixture(path, fixture):
    # 정렬하면 choice 삽입 순서 시험이 사라진다. 케이스/배치마다 한 줄로 보존한다.
    parts = ['{"schema":"t0_fixture/1","seed":' + str(fixture["seed"]) + ',"cases":[\n']
    parts.append(",\n".join(canonical_bytes(c).decode() for c in fixture["cases"]))
    parts.append('\n],"batches":[\n')
    parts.append(",\n".join(canonical_bytes(c).decode() for c in fixture["batches"]))
    parts.append("\n]}\n")
    write_bytes(path, "".join(parts).encode())
