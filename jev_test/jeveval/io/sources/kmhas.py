"""무엇: K-MHaS 읽기 · 입력: parquet 경로 · 출력: SourceRow 목록 · 계약 §6."""

from pathlib import Path
import json

import pyarrow.parquet as pq

from jeveval.types import SourceRow


def read_rows(source_cfg: dict, root: Path) -> list[SourceRow]:
    """물리 행 ID·정수 라벨을 보존하고 메타데이터 이름을 원래 순서로 붙인다."""
    table = pq.read_table(root / source_cfg["file"])
    try:
        names = json.loads((table.schema.metadata or {})[b"huggingface"])[
            "info"]["features"]["label"]["feature"]["names"]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("missing K-MHaS label names metadata") from exc
    if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
        raise ValueError("invalid K-MHaS label names")
    if len(set(names)) != len(names):
        raise ValueError("duplicate K-MHaS label names")
    fields = table.to_pylist()
    for row in fields:
        labels = row.get("label")
        if not isinstance(labels, list) or any(type(i) is not int or not 0 <= i < len(names)
                                                for i in labels):
            raise ValueError("K-MHaS label must contain integers in metadata range")
        row["label_names"] = [names[i] for i in labels]
    return [SourceRow("kmhas", str(i), row) for i, row in enumerate(fields)]
