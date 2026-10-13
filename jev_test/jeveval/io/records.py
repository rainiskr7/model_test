"""무엇: 기록 JSONL 입출력·끝 복구 · 입력: 경로·레코드 · 출력: 바이트/목록·경고 · 계약 §5-3·§5-5b."""

import json
import os
from pathlib import Path

from jeveval.types import AttemptRecord, FinalRecord


def record_line(record) -> bytes:
    return (json.dumps(record.to_dict(), ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def append_record(path, record) -> None:
    """부모 폴더를 만들지 않는다. resume 호출자는 먼저 repair_tail을 실행한다."""
    payload = record_line(record)
    with Path(path).open("ab") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def _lines(stream):
    """LF 기준 바이트 줄: 끝의 UTF-8 절단은 앞의 정상 줄을 손상시키지 않는다."""
    line = stream.readline()
    number = 0
    while line:
        number += 1
        following = stream.readline()
        yield number, line, not following
        line = following


def _read(path, cls):
    records, warnings = [], []
    try:
        stream = Path(path).open("rb")
    except FileNotFoundError:
        return records, warnings
    with stream:
        for number, line, last in _lines(stream):
            try:
                data = json.loads(line.decode("utf-8"))
            except ValueError as exc:
                if not last:
                    raise ValueError(f"line {number}: invalid JSON") from exc
                warnings.append("truncated_last_line")
                break
            try:
                records.append(cls.from_dict(data))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"line {number}: invalid record") from exc
            if last and not line.endswith(b"\n"):
                warnings.append("missing_final_newline")
    return records, warnings


def read_attempts(path) -> tuple[list[AttemptRecord], list[str]]:
    records, warnings = _read(path, AttemptRecord)
    previous = {}
    for number, record in enumerate(records, 1):
        last = previous.get(record.call_id)
        expected = last.attempt + 1 if last else 1
        if record.attempt != expected:
            raise ValueError(f"line {number}: duplicate or nonconsecutive attempt")
        if last and (last.terminal or last.logical_id != record.logical_id
                     or last.request_sha256 != record.request_sha256):
            raise ValueError(f"line {number}: attempt after terminal or changed call identity")
        previous[record.call_id] = record
    return records, warnings


def read_finals(path) -> tuple[list[FinalRecord], list[str]]:
    records, warnings = _read(path, FinalRecord)
    seen = set()
    for number, record in enumerate(records, 1):
        if record.logical_id in seen:
            raise ValueError(f"line {number}: duplicate logical_id")
        seen.add(record.logical_id)
    return records, warnings


def repair_tail(path) -> list[str]:
    """끝만 고치고 fsync한다. 중간 JSON 손상은 변경 없이 거부한다."""
    try:
        stream = Path(path).open("r+b")
    except FileNotFoundError:
        return []
    with stream:
        offset = 0
        for number, line, last in _lines(stream):
            try:
                json.loads(line.decode("utf-8"))
            except ValueError as exc:
                if not last:
                    raise ValueError(f"line {number}: invalid JSON") from exc
                stream.truncate(offset)
                warning = "truncated_last_line"
            else:
                if not last or line.endswith(b"\n"):
                    offset += len(line)
                    continue
                stream.seek(0, os.SEEK_END)
                stream.write(b"\n")
                warning = "missing_final_newline"
            stream.flush()
            os.fsync(stream.fileno())
            return [warning]
    return []
