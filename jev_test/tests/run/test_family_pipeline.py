"""무엇: kosgd2 가족 전체 경계 · 입력: 별칭 합성 실행 · 출력: 슬롯·서비스 집계 · 계약 §1-1."""

from jeveval.io import run_files
from jeveval.run import stage_inputs
from tests.run.history_support import finished


def test_alias_reader_items_score_risk_keep_identity_and_family_statistics(tmp_path, monkeypatch):
    h = finished(tmp_path, monkeypatch, "kosgd2", "full")
    items = stage_inputs.load_items(root=tmp_path, task_path="configs/tasks/kosgd2_full.yaml", stage="test")
    assert items[0].set == "kosgd2"
    assert sum(q.role == "success" for q in items[0].questions) == 10
    assert sum(q.role == "diagnostic" for q in items[0].questions) == 3
    assert next(q.gold for q in items[0].questions if q.id == "ongoing_two") == "false"
    score = run_files.read_json(h.directory / "scores.json")
    assert "bundle_correct" in score["populations"]["test"]["set_specific"]
    risk = run_files.read_json(h.directory / "risk.json")
    assert risk["cells"]["0.02"]["accepted_mix"]["by_service"] == {}


def test_item_summary_reuses_family_builder(tmp_path, monkeypatch, capsys):
    from jeveval.run.item_summary import main, BUILDERS
    from jeveval.run.stage_inputs import BUILDERS as shared
    h = finished(tmp_path, monkeypatch, "kosgd2", "full")
    capsys.readouterr()
    assert BUILDERS is shared
    assert main(["--root", str(tmp_path), "--task", "kosgd2_full"]) == 0
    assert '"task":"kosgd2_full"' in capsys.readouterr().out


def test_alias_actions_only_derives_same_action_questions(tmp_path, monkeypatch):
    from jeveval.io.config import load_taskspec
    h = finished(tmp_path, monkeypatch, "kosgd2", "full")
    h.variant = "actions_only"
    h.run("dev")
    assert h.command("threshold") == 0
    h.run("test")
    assert h.command("score") == 0
    full = load_taskspec(tmp_path / "configs/tasks/kosgd2_full.yaml")
    alias_actions = load_taskspec(tmp_path / "configs/tasks/kosgd2_actions_only.yaml")
    # W2 changes INFORM_INTENT only in kosgd2; compare its two variants.
    assert alias_actions.questions == [q for q in full.questions if q.id.startswith("act_")]
    assert len(alias_actions.questions) == 10
