"""무엇: 질문 위험 CLI와 단일 질문 동치 · 입력: 같은 KLUE run · 출력: 6필드 일치 · 계약 §7-4b."""

import pytest

from jeveval.io import run_files
from jeveval.run import cli, cmd_question_risk
from tests.run.history_support import finished


@pytest.mark.parametrize("historical", [False, True])
def test_one_question_same_ids_mask_validity_confidence_threshold_risk_equal(tmp_path, monkeypatch, historical):
    h = finished(tmp_path, monkeypatch)
    assert cli.main(["question-risk", "--run-dir", str(h.directory)] + (["--history"] if historical else [])) == 0
    output = run_files.read_json(h.directory / "question_risk.json")
    risk = run_files.read_json(h.directory / "risk.json")
    assert output["registration"]["status"] == "exploratory"
    assert len(output["registration"]["manifest_sha256"]) == 64
    for tau, cell in output["questions"]["answerable"]["by_tau"].items():
        request = risk["cells"][tau]
        assert cell == {k: request[k] if k in ("status", "t_star") else request["test"][k] for k in cell}


def test_history_missing_seal_never_writes(tmp_path, monkeypatch):
    h = finished(tmp_path, monkeypatch)
    (h.directory / "test/seal.json").unlink()
    with pytest.raises(ValueError):
        cmd_question_risk.run(root=tmp_path, run_dir=h.directory, history=True)
    assert not (h.directory / "question_risk.json").exists()
