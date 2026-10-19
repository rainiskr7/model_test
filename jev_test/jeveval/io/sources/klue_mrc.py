"""무엇: KLUE-MRC 읽기 · 입력: parquet 경로 · 출력: guid별 SourceRow · 계약 §6."""

from pathlib import Path

import pyarrow.parquet as pq

from jeveval.types import SourceRow


def read_rows(source_cfg: dict, root: Path, *, set_name="klue_mrc_answerable") -> list[SourceRow]:
    """is_impossible 여부와 관계없이 모든 행과 source를 보존한다."""
    fields = pq.read_table(root / source_cfg["file"]).to_pylist()
    return [SourceRow(set_name, row["guid"], row) for row in fields]
