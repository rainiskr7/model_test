"""무엇: K-MHaS 합성 원본 검사 · 입력: tmp_path parquet · 출력: 행·목록 검증 · 계약 §6."""

import pyarrow as pa
import pyarrow.parquet as pq

from jeveval.io.sources.kmhas import read_rows


def test_physical_row_ids_and_python_labels(tmp_path):
    data = [{"text": "문장", "label": [1, 2]}, {"text": "문장", "label": [8]}]
    pq.write_table(pa.Table.from_pylist(data), tmp_path / "part.parquet")
    rows = read_rows({"file": "part.parquet"}, tmp_path)
    assert [r.row_id for r in rows] == ["0", "1"]
    assert [r.fields for r in rows] == data
    assert rows[0].to_dict()["fields"]["label"] == [1, 2]
