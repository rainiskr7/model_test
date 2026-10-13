"""무엇: KOTE 합성 원본 검사 · 입력: tmp_path parquet · 출력: 라벨·메타데이터 검증 · 계약 §6."""

import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from jeveval.io.sources.kote import read_label_names, read_rows


def test_info_metadata_and_python_lists(tmp_path):
    names = ["화남/분노", "없음"]
    data = [{"ID": "original-id", "text": "문장", "labels": [0, 1]}]
    metadata = {b"huggingface": json.dumps({"info": {"features": {
        "labels": {"feature": {"names": names}}}}}).encode()}
    table = pa.Table.from_pylist(data).replace_schema_metadata(metadata)
    pq.write_table(table, tmp_path / "part.parquet")
    rows = read_rows({"file": "part.parquet"}, tmp_path)
    assert rows[0].row_id == "0"
    assert rows[0].to_dict()["fields"] == data[0]
    assert read_label_names({"file": "part.parquet"}, tmp_path) == names


def test_missing_metadata_fails(tmp_path):
    pq.write_table(pa.table({"labels": [[0]]}), tmp_path / "part.parquet")
    with pytest.raises(ValueError, match="metadata"):
        read_label_names({"file": "part.parquet"}, tmp_path)
