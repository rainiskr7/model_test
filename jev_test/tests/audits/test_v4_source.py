"""원본/선정/분할 연결과 두 lists 동시 변조를 실제 독립 로더로 검사한다."""

import json
from pathlib import Path
from copy import deepcopy

from audits.audit_v4.independent import source
from audits.audit_v4.run import base_rules, aggregate
from audits.audit_v4.evidence import MODELS


def put(root, name, value):
    p = root / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False))


def synthetic(root):
    rows = [dict(dialogue_id=f"d{i:04}", turns=[dict(speaker="USER", utterance="canary", frames=[])]) for i in range(4201)]
    ds = {d["dialogue_id"]: d for d in rows}
    old = [dict(dialogue_id=d["dialogue_id"], turn_index=0) for d in rows[:3000]]
    selected = source.selected_again(ds, {r["dialogue_id"] for r in old}, {"d3000"})
    schema = [dict(service_name="s", description="S", intents=[dict(name="A", description="a")])]
    cat = source.catalog(schema)
    put(root, "dataset/kosgd2/dialogues_001.json", rows)
    put(root, "dataset/kosgd2/extended_schema.json", schema)
    put(root, "audits/kosgd_audit/audit_result.json", dict(selected_turns=old))
    put(root, "audits/kosgd2_selection/selection.json", dict(selected_turns=selected))
    put(root, "configs/t0/fixture_v1.json", dict(cases=[dict(state_ref=dict(set="kosgd", row_id="d3000#0"))]))
    put(root, "configs/tasks/lists/kosgd_catalog.json", cat)
    put(root, "configs/tasks/lists/catalog_intents_plus_none.json", source.options(cat))
    ids = [r["dialogue_id"] for r in selected]
    put(root, "configs/splits/kosgd2.json", dict(set="kosgd2", dev=ids[:240], test=ids[240:],
        representative={i: f"kosgd2:{i}:0" for i in ids}))
    return cat


def test_shared_lists_corruption_is_audit_fail(tmp_path):
    cat = synthetic(tmp_path)
    assert all(source.load(tmp_path, "kosgd2")[-1].values())
    cat[0]["intents"][0]["description"] = "both changed"
    put(tmp_path, "configs/tasks/lists/kosgd_catalog.json", cat)
    put(tmp_path, "configs/tasks/lists/catalog_intents_plus_none.json", source.options(cat))
    assert source.load(tmp_path, "kosgd2")[-1]["lists"] is False
    models = {m: dict(variants={v: {r: "PASS" for r in ("R4", "R7", "R2v3", "v4_hash")}
              for v in ("full", "actions_only")}) for m in MODELS}
    audited = aggregate(base_rules(tmp_path, "kosgd2"), models, dict(status="PASS"))
    assert audited["full"]["R4"]["status"] == "FAIL"


def test_selection_and_split_must_cover_same_ids(tmp_path):
    synthetic(tmp_path)
    path = tmp_path / "configs/splits/kosgd2.json"
    plan = json.loads(path.read_text())
    plan["test"][-1] = plan["dev"][0]
    put(tmp_path, "configs/splits/kosgd2.json", plan)
    assert source.load(tmp_path, "kosgd2")[-1]["split"] is False
