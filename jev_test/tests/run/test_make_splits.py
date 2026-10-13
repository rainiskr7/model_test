"""무엇: CLI 통합 검증 · 입력: tmp_path의 여섯 합성 셋 · 출력: 분할/재현성/실패 · 계약 §6·§8."""

import json
from pathlib import Path
import subprocess
import sys

import pyarrow as pa
import pyarrow.parquet as pq
import yaml


REPO = Path(__file__).resolve().parents[2]
BOOTSTRAP = "import runpy,sys; sys.path.insert(0,sys.argv.pop(1)); runpy.run_module('jeveval.run.make_splits',run_name='__main__')"


def _parquet(root, name, rows, metadata=None):
    table = pa.Table.from_pylist(rows)
    if metadata:
        table = table.replace_schema_metadata(metadata)
    pq.write_table(table, root / f"{name}.parquet")
    return {"source": {"file": f"{name}.parquet"}, "unit": "row",
            "group_key": "text", "pool": {"kind": "simple_cap", "cap": 5}}


def _synthetic_json(root):
    directory = root / "kosgd"
    directory.mkdir()
    dialogue = [{"dialogue_id": f"d{i}", "turns": [
        {"speaker": "USER", "utterance": "시작", "frames": []},
        {"speaker": "SYSTEM", "utterance": "응답", "frames": []},
        {"speaker": "USER", "utterance": "다음", "frames": []}]} for i in range(6)]
    (directory / "dialogues_001.json").write_text(json.dumps(dialogue))
    (root / "selection.json").write_text(json.dumps({"selected_turns": [
        {"dialogue_id": f"d{i}", "turn_index": 2} for i in range(5)]}))
    rows = [{"serial_num": i + 1, "input_messages": [
        {"role": "system", "content": "공통 시스템"}, {"role": "user", "content": f"요청{i}"}],
        "input_tools": [{"type": "function", "function": {"name": f"tool{i}"}}]}
        for i in range(6)]
    rows.append({**rows[0], "serial_num": 7})
    (root / "fc.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
    return {
        "kosgd": {"source": {"dir": "kosgd", "dialogues_glob": "dialogues_*.json"},
                  "group_key": "dialogue_id", "pool": {"kind": "fixed_selection",
                  "path": "selection.json", "field": "selected_turns"}},
        "fc_call_decision": {"source": {"file": "fc.jsonl"}, "group_key": "fc_components",
                             "expect_groups": 6, "pool": {"kind": "all"}, "extra": True}}


def _synthetic_rules(root):
    sets = _synthetic_json(root)
    sets["kmhas"] = _parquet(root, "kmhas", [{"text": f"문장{i}", "label": [i % 2]} for i in range(6)])
    sets["kmhas"]["label_field"] = "label"
    sets["kote_escalation"] = _synthetic_kote(root)
    sets["korfin_asc"] = _parquet(root, "korfin", [
        {"SID": f"{i}_{j}", "SRC": f"문장{i}", "ASPECT": f"대상{j}", "SENTIMENT": "positive"}
        for i in range(6) for j in range(2)])
    sets["korfin_asc"].update(unit="src", group_key="SRC")
    sets["klue_mrc_answerable"] = _parquet(root, "klue", [
        {"guid": f"g{i}", "context": f"문맥{i}", "source": "news" if i % 2 else "wiki",
         "question": "질문", "is_impossible": bool(i % 2)} for i in range(6)])
    sets["klue_mrc_answerable"].update(group_key="context", pool={
        "kind": "proportional", "cap": 5, "stratum_field": "source"})
    rules = {"seed": 20261012, "dev_fraction": 0.2, "sets": sets}
    (root / "rules.yaml").write_text(yaml.safe_dump(rules, allow_unicode=True))
    return rules


def _synthetic_kote(root):
    names = ["화남/분노", "없음"] + [f"합성감정{i}" for i in range(42)]
    metadata = {b"huggingface": json.dumps({"info": {"features": {
        "labels": {"feature": {"names": names}}}}}).encode()}
    rows = [{"ID": 100 + i, "text": f"문장{i}", "labels": [0, 1]} for i in range(6)]
    rows.append({"ID": 106, "text": "문장0", "labels": [0, 1]})
    raw = {str(r["ID"]): {"text": r["text"], "labels": {
        "rater1": ["화남/분노", "화남/분노", "없음"], "rater2": ["없음"],
        "rater3": ["없음"], "rater4": [], "rater5": []}} for r in rows}
    raw["106"]["labels"]["rater2"] = []
    (root / "raw.json").write_text(json.dumps(raw), encoding="utf-8")
    cfg = _parquet(root, "kote", rows, metadata)
    cfg["source"]["votes"] = "raw.json"
    cfg.update(label_field="labels_majority", votes={"n_raters": 5, "min_raters": 3},
               demotion={"emotions": ["화남/분노", "없음"], "min_positive": 1,
                         "label_names": "parquet_metadata"})
    return cfg


def _run(root, output, selection="all"):
    return subprocess.run([sys.executable, "-I", "-c", BOOTSTRAP, str(REPO),
                           "--rules", "rules.yaml", "--root", str(root), "--set", selection,
                           "--out", str(output)], text=True, capture_output=True, cwd=root)


def test_all_synthetic_sets_twice_identical_bytes(tmp_path):
    rules = _synthetic_rules(tmp_path)
    output = tmp_path / "out"
    first = _run(tmp_path, output)
    assert first.returncode == 0, first.stderr
    before = {p.name: p.read_bytes() for p in output.glob("*.json")}
    second = _run(tmp_path, output)
    assert second.returncode == 0, second.stderr
    assert second.stdout == first.stdout
    assert before == {p.name: p.read_bytes() for p in output.glob("*.json")}
    assert set(before) == {f"{s}.json" for s in rules["sets"]}
    assert len(first.stdout.splitlines()) == 6
    for name, raw in before.items():
        plan = json.loads(raw)
        assert plan["pool_rule"] == rules["sets"][name[:-5]]["pool"]
        assert plan["dev"] == sorted(plan["dev"]) and plan["test"] == sorted(plan["test"])
        assert set(plan["dev"]).isdisjoint(plan["test"])
        assert set(plan["dev"] + plan["test"]) == set(plan["groups"])
    assert json.loads(before["klue_mrc_answerable.json"])["notes"]["n_rows"] == 6
    assert json.loads(before["korfin_asc.json"])["notes"]["n_rows"] == 12
    assert len(json.loads(before["fc_call_decision.json"])["extra"]) == 1
    kote = json.loads(before["kote_escalation.json"])
    assert kote["diagnostic_demotions"] == ["화남/분노"]
    assert kote["notes"]["label_conflict_groups_total"] == 1


def test_single_set_and_expect_groups_failure(tmp_path):
    rules = _synthetic_rules(tmp_path)
    output = tmp_path / "out"
    result = _run(tmp_path, output, "kmhas")
    assert result.returncode == 0, result.stderr
    assert [p.name for p in output.iterdir()] == ["kmhas.json"]
    rules["sets"]["fc_call_decision"]["expect_groups"] = 107
    (tmp_path / "rules.yaml").write_text(yaml.safe_dump(rules))
    result = _run(tmp_path, output, "fc_call_decision")
    assert result.returncode != 0
    assert "expected 107 groups, got 6" in result.stderr
    assert not (output / "fc_call_decision.json").exists()


def test_kote_votes_setting_and_invalid_raw_stop_cli(tmp_path):
    rules = _synthetic_rules(tmp_path)
    output = tmp_path / "out"
    rules["sets"]["kote_escalation"]["votes"]["min_raters"] = 1
    (tmp_path / "rules.yaml").write_text(yaml.safe_dump(rules))
    result = _run(tmp_path, output, "kote_escalation")
    assert result.returncode == 0, result.stderr
    plan = json.loads((output / "kote_escalation.json").read_text())
    assert plan["diagnostic_demotions"] == []
    assert plan["notes"]["label_conflict_groups_total"] == 0
    raw = json.loads((tmp_path / "raw.json").read_text())
    del raw["106"]
    (tmp_path / "raw.json").write_text(json.dumps(raw))
    result = _run(tmp_path, tmp_path / "failed", "kote_escalation")
    assert result.returncode != 0
    assert "KOTE raw missing ID: 106" in result.stderr
    assert not (tmp_path / "failed" / "kote_escalation.json").exists()
