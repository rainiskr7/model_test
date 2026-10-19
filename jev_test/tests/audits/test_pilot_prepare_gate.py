"""파일럿 전체 사슬의 정답 미접근·호출 집계·정식 열거 격리."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from audits.audit_v4.offline import guard
from audits.kosgd2_pilot.select_pilot import select, digest
from audits.kosgd2_pilot.prepare import plans, manifest
from audits.kosgd2_pilot.gate import evaluate
from jeveval.io import archive, history
from tests.audits.pilot_support import dialogues, responses

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def pilot(tmp_path, monkeypatch):
    def forbidden(*a, **kw): raise AssertionError("gold accessed")
    monkeypatch.setattr("jeveval.score.labels.gold", forbidden)
    source = dialogues()
    selected = select(source, [dict(dialogue_id=d["dialogue_id"]) for d in source], set(), set())
    value = dict(selected_turns=selected, selection_sha256=digest(selected))
    path = tmp_path / "dialogues_001.json"
    path.write_text(json.dumps(source))
    with guard():
        planned = plans(ROOT, tmp_path, value)
    return source, value, planned, path


def test_label_erasure_and_mutation_leave_whole_chain_unchanged(pilot):
    source, selection, planned, path = pilot
    before = manifest(ROOT, selection, planned)
    expected = evaluate(planned, responses(planned))
    for d in source:
        d["services"] = ["poison"]
        for t in d["turns"]: t.update(frames=[{"state": "poison", "actions": ["poison"]}], state="poison", actions="poison")
    path.write_text(json.dumps(source))
    with guard():
        selected = select(source, [dict(dialogue_id=d["dialogue_id"]) for d in source], set(), set())
        changed = plans(ROOT, path.parent, dict(selected_turns=selected, selection_sha256=digest(selected)))
        assert manifest(ROOT, selection, changed) == before
        assert evaluate(changed, responses(changed)) == expected
    assert expected["status"] == "PASS"


@pytest.mark.parametrize("duplicates,invalid,status", [(10, 0, "PASS"), (11, 0, "FAIL"), (0, 10, "PASS"), (0, 11, "FAIL")])
def test_gate_fixed_denominator_boundaries(pilot, duplicates, invalid, status):
    _, _, planned, _ = pilot
    result = evaluate(planned, responses(planned, duplicates=duplicates, invalid=invalid))
    assert result["status"] == status
    assert all(r["denominator"] == 200 for r in result["models"].values())


def test_missing_duplicate_extra_and_partial_b1(pilot):
    _, _, planned, _ = pilot
    raw = responses(planned)
    raw["b1_qwen3_8_27b"][0]["calls"][5]["http_status"] = 500
    assert evaluate(planned, raw)["models"]["b1_qwen3_8_27b"]["invalid"] == 1
    raw["b1_qwen3_8_27b"][0]["calls"].pop()
    assert evaluate(planned, raw)["status"] == "INCOMPLETE"
    raw = responses(planned)
    raw["pplx_v1_1"].pop()
    assert evaluate(planned, raw)["status"] == "INCOMPLETE"
    raw["pplx_v1_1"].append(raw["pplx_v1_1"][0])
    with pytest.raises(ValueError): evaluate(planned, raw)
    raw["pplx_v1_1"][-1] = dict(logical_id="extra", calls=[])
    with pytest.raises(ValueError): evaluate(planned, raw)


def test_pilot_results_are_not_formal_run_directories(tmp_path):
    p = tmp_path / "results/_pilot/kosgd2_w1/b1_qwen3_8_27b/r1"
    p.mkdir(parents=True)
    (p / "raw.json").write_text("{}")
    assert history.variants(tmp_path, "results", "b1_qwen3_8_27b", "r1") == []
    assert archive.run_directories(tmp_path, "results", "r1") == []
