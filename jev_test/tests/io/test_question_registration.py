"""manifest는 저장 fingerprint에 묶인 것만 읽는다."""

from jeveval.io import question_registration as io
from tests.run.registration_support import registered


def test_modified_manifest_is_damaged_input(tmp_path, monkeypatch):
    h = registered(tmp_path, monkeypatch)
    p = tmp_path / "configs/analysis/question_risk_v2.yaml"
    p.write_text(p.read_text() + "\n# changed\n")
    assert io.read(tmp_path, h.directory)["errors"]


def test_unrelated_manifest_never_changes_registered_selection(tmp_path, monkeypatch):
    h = registered(tmp_path, monkeypatch)
    before = io.read(tmp_path, h.directory)
    (tmp_path / "configs/analysis/unrelated.yaml").write_text("[broken")
    assert io.read(tmp_path, h.directory) == before


def test_malformed_registered_manifest_is_damaged_without_raw_exception(tmp_path, monkeypatch):
    h = registered(tmp_path, monkeypatch)
    (tmp_path / "configs/analysis/question_risk_v2.yaml").write_text("secret: [")
    assert io.read(tmp_path, h.directory)["errors"] == ["invalid_registration_inputs"]
