"""무엇: FunctionChat 읽기 · 입력: JSONL 경로 · 출력: SourceRow 목록 · 계약 §6."""

import json
from pathlib import Path

from jeveval.types import SourceRow


def read_rows(source_cfg: dict, root: Path) -> list[SourceRow]:
    """메시지·중첩 도구를 원형대로 보존하고 serial을 문자열 ID로 쓴다."""
    rows = []
    with (root / source_cfg["file"]).open(encoding="utf-8") as stream:
        for line in stream:
            fields = json.loads(line)
            if type(fields["serial_num"]) is not int:
                raise ValueError("serial_num must be an integer")
            rows.append(SourceRow("fc_call_decision", str(fields["serial_num"]), fields))
    return rows
