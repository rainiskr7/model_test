"""무엇: K-MHaS 읽기 · 입력: parquet 경로 · 출력: SourceRow 목록 · 계약 §6."""

from pathlib import Path

import pyarrow.parquet as pq

from jeveval.types import SourceRow


def read_rows(source_cfg: dict, root: Path) -> list[SourceRow]:
    """물리 행 위치를 ID로 쓰고 label 목록을 Python 값으로 반환한다."""
    fields = pq.read_table(root / source_cfg["file"]).to_pylist()
    return [SourceRow("kmhas", str(i), row) for i, row in enumerate(fields)]
