"""무엇: KorFin 합성 원본 검사 · 입력: tmp_path parquet · 출력: SID·aspect 순서 검증 · 계약 §6."""

import pyarrow as pa
import pyarrow.parquet as pq

from jeveval.data.grouping import group_rows
from jeveval.io.sources.korfin import read_rows


def test_sid_rows_preserved_but_members_are_src_items(tmp_path):
    data = [{"SID": "4208_1", "SRC": "문장", "ASPECT": "둘", "SENTIMENT": "positive"},
            {"SID": "4208_0", "SRC": "문장", "ASPECT": "하나", "SENTIMENT": "negative"}]
    pq.write_table(pa.Table.from_pylist(data), tmp_path / "part.parquet")
    rows = read_rows({"file": "part.parquet"}, tmp_path)
    assert [r.fields for r in rows] == data
    groups = group_rows(rows, "SRC")
    assert groups.members == {"4208": ["4208"]}
    assert groups.row_to_group == {"4208_0": "4208", "4208_1": "4208"}
