"""무엇: KorFin-ASC 읽기 · 입력: parquet 경로 · 출력: SID별 SourceRow · 계약 §6."""

from pathlib import Path

import pyarrow.parquet as pq

from jeveval.types import SourceRow


def read_rows(source_cfg: dict, root: Path, *, set_name="korfin_asc") -> list[SourceRow]:
    """aspect 행을 원본 순서대로 유지한다. SRC 축약은 grouping이 맡는다."""
    fields = pq.read_table(root / source_cfg["file"]).to_pylist()
    return [SourceRow(set_name, row["SID"], row) for row in fields]
