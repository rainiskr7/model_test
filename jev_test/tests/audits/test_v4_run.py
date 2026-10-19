"""감사 모델 합성 결과의 적용 범위·실패 우선·주입 게이트 집계."""

from audits.audit_v4.run import aggregate, base_rules
from audits.audit_v4.evidence import MODELS


def test_unrun_model_is_not_a_pass_and_range_failure_is_preserved():
    models = {m: dict(variants={v: dict(R4="PASS", R7="PASS", v4_hash="PASS", R2v3=dict(status="PASS"))
                               for v in ("full", "actions_only")}) for m in MODELS}
    models["clef"]["variants"]["full"]["R2v3"]["status"] = "INCOMPLETE"
    base = {v: dict(R5=dict(status="FAIL"), R6=dict(status="PASS"), source_links={"x": True}) for v in ("full", "actions_only")}
    result = aggregate(base, models, dict(status="PASS"))
    assert result["full"]["R5"]["status"] == "FAIL"
    assert result["full"]["R2v3"]["status"] == "INCOMPLETE"
    assert result["actions_only"]["v4_hash"]["status"] == "PASS"


def test_absent_real_source_is_incomplete(tmp_path):
    assert base_rules(tmp_path, "kosgd2")["full"]["R5"]["status"] == "INCOMPLETE"
