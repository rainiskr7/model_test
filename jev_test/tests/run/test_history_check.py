"""무엇: 역사 무결성 반례 · 입력: 합성 완료 run · 출력: 검증/미완/손상 · 계약 §5-1b."""

import pytest

from jeveval.io import history, run_files
from jeveval.run.history_check import check
from tests.run.history_support import finished


@pytest.mark.parametrize("fault,expected", [
    ("none", "verified_complete"), ("model", "damaged"), ("run_id", "damaged"),
    ("task", "damaged"), ("no_seal", "incomplete"), ("seal", "damaged"),
    ("risk_hash", "damaged"), ("duplicate", "damaged"), ("extra", "damaged"),
    ("middle", "damaged"), ("tail", "incomplete"), ("missing", "incomplete"),
    ("split_changed", "incomplete"), ("code_changed", "verified_complete")])
def test_historical_evidence_classification(tmp_path, monkeypatch, fault, expected):
    h = finished(tmp_path, monkeypatch)
    if fault in ("model", "run_id", "risk_hash"):
        path = h.directory / "risk.json"
        value = run_files.read_json(path)
        value[{"risk_hash": "threshold_sha256"}.get(fault, fault)] = "x"
        run_files.write_json(path, value)
    elif fault == "task":
        path = h.directory / "fingerprint.json"
        value = run_files.read_json(path)
        value["inputs"]["task_path"] = "wrong.yaml"
        run_files.write_json(path, value)
    elif fault == "no_seal":
        (h.directory / "test/seal.json").unlink()
    elif fault == "seal":
        run_files.write_json(h.directory / "test/seal.json", {"threshold_sha256": "bad"})
    elif fault in ("duplicate", "extra", "middle", "tail", "missing"):
        path = h.directory / "test/final.jsonl"
        payload = path.read_text()
        changed = payload.replace('"logical_id":"klue_mrc_answerable:2:2"', '"logical_id":"klue_mrc_answerable:9:9"')
        path.write_text({"duplicate": payload * 2, "extra": payload + changed,
                         "middle": "{bad\n" + payload, "tail": payload + "{bad", "missing": ""}[fault])
    elif fault == "split_changed":
        with (h.root / "configs/splits/klue_mrc_answerable.json").open("a") as stream:
            stream.write(" ")
    elif fault == "code_changed":
        (h.root / "jeveval/new.py").write_text("new historical reader")
    saved = history.read(h.root, h.directory)
    assert check(saved).status == expected


def test_current_code_or_common_config_does_not_invalidate_historical_read(tmp_path, monkeypatch):
    h = finished(tmp_path, monkeypatch)
    path = tmp_path / "configs/datasets.yaml"
    path.write_text(path.read_text() + "\n# later family registration\n")
    assert check(history.read(tmp_path, h.directory)).status == "verified_complete"


def test_derived_source_marker_must_match_final_and_identity(tmp_path, monkeypatch):
    h = finished(tmp_path, monkeypatch)
    run_files.write_json(h.directory / "test/derived.json", {"derived_from": "PRIVATE_RAW"})
    assert check(history.read(tmp_path, h.directory)).status == "damaged"
