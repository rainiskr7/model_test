"""무엇: KOTE 합성 원본 검사 · 입력: tmp_path parquet/raw · 출력: 투표·멈춤 조건 검증 · 계약 §6."""

import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from jeveval.io.sources.kote import read_label_names, read_rows


NAMES = ["화남/분노", "없음", "고마움"] + [f"합성감정{i}" for i in range(41)]
SOURCE = {"file": "part.parquet", "votes": "raw.json"}
VOTES = {"n_raters": 5, "min_raters": 3}


def _raw_record(text="문장"):
    return {"text": text, "labels": {
        "rater1": ["화남/분노", "화남/분노", "없음", "고마움"],
        "rater2": ["화남/분노", "없음"], "rater3": ["없음"],
        "rater4": [], "rater5": []}}


def _write(tmp_path, raw=None):
    data = [{"ID": 72, "text": "문장", "labels": [0, 2]},
            {"ID": 9, "text": "다른 문장", "labels": []}]
    metadata = {b"huggingface": json.dumps({"info": {"features": {
        "labels": {"feature": {"names": NAMES}}}}}).encode()}
    table = pa.Table.from_pylist(data).replace_schema_metadata(metadata)
    pq.write_table(table, tmp_path / "part.parquet")
    if raw is None:
        raw = {"9": _raw_record("다른 문장"), "72": _raw_record()}
        raw["9"]["labels"]["rater3"] = ["화남/분노", "없음"]
    (tmp_path / "raw.json").write_text(json.dumps(raw), encoding="utf-8")
    return data


def test_majority_boundary_duplicates_and_id_lookup(tmp_path):
    data = _write(tmp_path)
    rows = read_rows(SOURCE, tmp_path, VOTES)
    assert [row.row_id for row in rows] == ["0", "1"]
    assert rows[0].fields == {**data[0], "votes": {"화남/분노": 2, "없음": 3, "고마움": 1},
                              "labels_majority": ["없음"]}
    assert rows[1].fields == {**data[1], "votes": {"화남/분노": 3, "없음": 3, "고마움": 1},
                              "labels_majority": sorted(["화남/분노", "없음"])}
    assert read_label_names(SOURCE, tmp_path) == NAMES


@pytest.mark.parametrize("case,message", [
    ("missing_id", "missing ID"), ("text", "text mismatch"),
    ("too_few", "rater count"), ("too_many", "rater count"),
    ("unknown_emotion", "unknown emotion")])
def test_raw_stop_conditions(tmp_path, case, message):
    raw = {"72": _raw_record(), "9": _raw_record("다른 문장")}
    record = raw["9"]
    if case == "missing_id":
        del raw["9"]
    elif case == "text":
        record["text"] += " "
    elif case == "too_few":
        del record["labels"]["rater5"]
    elif case == "too_many":
        record["labels"]["rater6"] = []
    else:
        record["labels"]["rater5"] = ["메타데이터 밖"]
    _write(tmp_path, raw)
    with pytest.raises(ValueError, match=message):
        read_rows(SOURCE, tmp_path, VOTES)


@pytest.mark.parametrize("minimum", [0, -1, 6, 3.0, "3", True, False, None])
def test_invalid_min_raters(tmp_path, minimum):
    _write(tmp_path)
    with pytest.raises(ValueError, match="min_raters"):
        read_rows(SOURCE, tmp_path, {**VOTES, "min_raters": minimum})


@pytest.mark.parametrize("minimum,expected", [
    (1, sorted(["고마움", "없음", "화남/분노"])), (2, ["없음", "화남/분노"]), (5, [])])
def test_configured_threshold_endpoints(tmp_path, minimum, expected):
    _write(tmp_path)
    rows = read_rows(SOURCE, tmp_path, {**VOTES, "min_raters": minimum})
    assert rows[0].fields["labels_majority"] == expected


def test_configured_rater_count(tmp_path):
    record = _raw_record()
    del record["labels"]["rater5"]
    _write(tmp_path, {"72": record, "9": {**record, "text": "다른 문장"}})
    rows = read_rows(SOURCE, tmp_path, {"n_raters": 4, "min_raters": 3})
    assert rows[0].fields["labels_majority"] == ["없음"]


def test_missing_metadata_fails(tmp_path):
    pq.write_table(pa.table({"labels": [[0]]}), tmp_path / "part.parquet")
    with pytest.raises(ValueError, match="metadata"):
        read_label_names({"file": "part.parquet"}, tmp_path)
