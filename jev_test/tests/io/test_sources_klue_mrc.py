"""무엇: KLUE 합성 원본 검사 · 입력: tmp_path parquet · 출력: 양·음성 유지 검증 · 계약 §6."""

import pyarrow as pa
import pyarrow.parquet as pq

from jeveval.io.sources.klue_mrc import read_rows


def test_impossible_rows_and_guid_preserved(tmp_path):
    data = [{"guid": f"g{i}", "context": "문맥", "source": "wiki", "is_impossible": flag,
             "answers": {"text": ["답"], "answer_start": [0]}}
            for i, flag in enumerate([False, True])]
    pq.write_table(pa.Table.from_pylist(data), tmp_path / "part.parquet")
    rows = read_rows({"file": "part.parquet"}, tmp_path)
    assert [r.row_id for r in rows] == ["g0", "g1"]
    assert [r.to_dict()["fields"] for r in rows] == data
