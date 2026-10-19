"""무엇: 분석 등록 경계 · 입력: manifest · 출력: exploratory 해시 · 계약 §7-4b."""

from pathlib import Path

from jeveval.io.analysis import policy


def test_phase_a_manifest_is_exploratory_and_hashed():
    value, digest = policy(Path(__file__).resolve().parents[2])
    assert value["status"] == "exploratory" and len(digest) == 64
    assert value["claims"]["simultaneous"] is False


def test_declared_policy_cannot_silently_change_implemented_loss(tmp_path):
    import shutil
    import yaml
    import pytest
    source = Path(__file__).resolve().parents[2] / "configs/analysis/question_risk_v1.yaml"
    target = tmp_path / "configs/analysis/question_risk_v1.yaml"
    target.parent.mkdir(parents=True)
    value = yaml.safe_load(source.read_text())
    value["loss"] = "different"
    target.write_text(yaml.safe_dump(value))
    with pytest.raises(ValueError):
        policy(tmp_path)
