"""입력: 합성 원본·임시 Arrow/JSON. 출력: manifest 생성·무결성·오프라인 검증."""

from copy import deepcopy
import hashlib
import json

import pyarrow as pa
import pyarrow.ipc as ipc
import pytest

from shared.multimodal.rescore.manifest import (
    DATASETS, build_manifest, load_manifest, main, read_cache, validate_manifest,
)
from shared.multimodal.tests.test_rescore_kmmbench_circular_units import circular_case
from shared.multimodal.tests.test_rescore_mtvqa_lmms_units import mtvqa_case


def test_image_clusters_preserve_two_dtc_questions_and_shared_circular_images():
    raw = [{"index": f"document_{i}", "question": str(i), "answer": "A",
            "image": {"bytes": b"same"}} for i in range(2)]
    manifest = build_manifest("k_dtcbench", raw, {})
    assert manifest["counts"]["images"] == 1
    assert manifest["items"]["document_0"]["cluster"] == hashlib.sha256(b"same").hexdigest()[:16]
    assert manifest["items"]["document_1"]["cluster"] == manifest["items"]["document_0"]["cluster"]
    raw = [{**r, "index": i, "A": "a", "B": "b"} for i, r in enumerate(raw, 1)]
    manifest = build_manifest("k_mmbench", raw, {})
    assert manifest["counts"]["groups"] == 2 and manifest["counts"]["images"] == 1


def test_korean_filter_and_position_keys():
    rows = [
        {"id": "EN_0", "lang": "EN", "image": {"bytes": b"en"}, "qa_pairs": []},
        {"id": "KR_0", "lang": "KR", "image": {"bytes": b"kr"},
         "qa_pairs": "[{'question': 'q', 'answer': 'a'}, {'question': 'q2', 'answer': 'b'}]"},
    ]
    manifest = build_manifest("mtvqa_kr", rows, {})
    assert set(manifest["items"]) == {"KR_0\t0", "KR_0\t1"}
    assert manifest["items"]["KR_0\t1"]["row_idx"] == 0
    assert manifest["counts"]["images"] == 1


@pytest.mark.parametrize("field", ["revision", "counts", "groups", "images", "schema_version"])
def test_manifest_tampering_rejected(field):
    _, manifest = circular_case()
    value = deepcopy(manifest)
    value[field] = {} if field in ("counts", "groups", "images") else "bad"
    with pytest.raises((ValueError, KeyError)):
        validate_manifest(value)


def test_load_binds_exact_bytes_and_rejects_revision_and_malformed_json(tmp_path):
    _, manifest = mtvqa_case()
    revision = DATASETS["mtvqa_kr"][1]
    path = tmp_path / f"mtvqa_kr_{revision}.json"
    raw = json.dumps(manifest).encode()
    path.write_bytes(raw)
    loaded, digest = load_manifest("mtvqa_kr", revision, tmp_path)
    assert loaded == manifest and digest == hashlib.sha256(raw).hexdigest()
    with pytest.raises(ValueError, match="revision"):
        load_manifest("mtvqa_kr", "../bad", tmp_path)
    path.write_text("[]")
    with pytest.raises(ValueError):
        load_manifest("mtvqa_kr", revision, tmp_path)


def test_offline_cache_reader_only_uses_expected_revision(tmp_path, monkeypatch):
    for key in ("HF_DATASETS_OFFLINE", "HF_HUB_OFFLINE"):
        monkeypatch.setenv(key, "1")
    _, revision, split, folder, stem = DATASETS["mtvqa_kr"]
    directory = tmp_path / folder / "default/0.0.0" / revision
    directory.mkdir(parents=True)
    table = pa.Table.from_pylist([
        {"id": "EN_0", "lang": "EN", "image": {"bytes": b"en"}, "qa_pairs": "[]"},
        {"id": "KR_0", "lang": "KR", "image": {"bytes": b"kr"},
         "qa_pairs": "[{'question': 'q', 'answer': 'a'}]"},
    ])
    path = directory / f"{stem}-{split}.arrow"
    with path.open("wb") as stream, ipc.new_stream(stream, table.schema) as writer:
        writer.write_table(table)
    # An entire shard can have no Korean rows; empty indices must not infer null.
    shard = directory / f"{stem}-{split}-other.arrow"
    with shard.open("wb") as stream, ipc.new_stream(stream, table.schema) as writer:
        writer.write_table(table.slice(0, 1))
    rows, provenance = read_cache("mtvqa_kr", tmp_path)
    assert [r["id"] for r in rows] == ["KR_0"]
    assert {f["name"]: f["sha256"] for f in provenance["cache_files"]}[path.name] == hashlib.sha256(path.read_bytes()).hexdigest()
    monkeypatch.delenv("HF_HUB_OFFLINE")
    with pytest.raises(ValueError, match="OFFLINE"):
        read_cache("mtvqa_kr", tmp_path)


def test_builder_cli_orchestrates_without_touching_real_cache(monkeypatch, tmp_path, capsys):
    import shared.multimodal.rescore.manifest as module
    import shared.multimodal.rescore.sessions as sessions

    monkeypatch.setattr(module, "__file__", str(tmp_path / "manifest.py"))
    monkeypatch.setattr(sessions, "check_revisions", lambda *args: 1)
    rows = [{"index": "document_0", "question": "q", "answer": "A", "image": {"bytes": b"x"}}]
    monkeypatch.setattr(module, "read_cache", lambda *args: (rows, {"offline": True}))
    assert main(["--build", "k_dtcbench", "--base", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out)["items"] == 1
    assert len(list((tmp_path / "manifests").glob("*.json"))) == 1


def test_missing_offline_cache_fails(monkeypatch, tmp_path):
    monkeypatch.setenv("HF_DATASETS_OFFLINE", "1")
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    with pytest.raises(ValueError, match="missing"):
        read_cache("k_mmbench", tmp_path)
