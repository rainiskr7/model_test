"""무엇: K-MHaS 합성 원본 검사 · 입력: tmp_path parquet · 출력: 행·목록 검증 · 계약 §6."""

import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from jeveval.io.sources.kmhas import read_rows


def _write(tmp_path, data, names):
    table = pa.Table.from_pylist(data)
    metadata = {b"huggingface": json.dumps({"info": {"features": {
        "label": {"feature": {"names": names}}}}}).encode()}
    pq.write_table(table.replace_schema_metadata(metadata), tmp_path / "part.parquet")


def test_physical_row_ids_and_python_labels(tmp_path):
    data = [{"text": "문장", "label": [2, 1]}, {"text": "문장", "label": []}]
    _write(tmp_path, data, ["origin", "physical", "politics"])
    rows = read_rows({"file": "part.parquet"}, tmp_path)
    assert [r.row_id for r in rows] == ["0", "1"]
    assert rows[0].fields == {**data[0], "label_names": ["politics", "physical"]}
    assert rows[1].fields == {**data[1], "label_names": []}
    assert rows[0].to_dict()["fields"]["label"] == [2, 1]


@pytest.mark.parametrize("labels", [[-1], [2], [True], None, ["0"]])
def test_invalid_labels_stop(tmp_path, labels):
    _write(tmp_path, [{"text": "문장", "label": labels}], ["origin", "physical"])
    with pytest.raises(ValueError):
        read_rows({"file": "part.parquet"}, tmp_path)


def test_no_metadata_default(tmp_path):
    pq.write_table(pa.table({"label": [[0]]}), tmp_path / "part.parquet")
    with pytest.raises(ValueError, match="metadata"):
        read_rows({"file": "part.parquet"}, tmp_path)
