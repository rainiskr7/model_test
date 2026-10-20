"""무엇: 감사 증거 적격 판정 · 입력: 읽힌 감사/fingerprint · 출력: 규칙·연결 여부 · 계약 §7-6."""

import re

RULES = ("R2v3", "R4", "R5", "R6", "R7", "v4_hash")
STATES = {"PASS", "FAIL", "INCOMPLETE", "NOT_APPLICABLE"}


def select_audit_evidence(value, fp):
    """판 선택은 호출자가 한다. 사후 run의 set은 감사 최상위 set으로도 결합된다."""
    name = fp["set"]
    if value["schema"] != "audit_v4/1" or value["set"] != name or value["profile"] != name:
        raise ValueError("audit identity")
    required = {fp["inputs"]["task_path"], f"configs/splits/{name}.json", "configs/tasks/b1.yaml"}
    required.update(p for p in fp["files"] if p.startswith("configs/tasks/lists/"))
    if any(not fp["files"].get(p) or value["inputs"]["files"].get(p) != fp["files"][p] for p in required):
        raise ValueError("audit inputs differ")
    digest = value["code"]["audit_sha256"]
    if not isinstance(digest, str) or re.fullmatch("[0-9a-f]{64}", digest) is None:
        raise ValueError("audit digest")
    if value["models"][fp["model"]]["variants"][fp["variant"]]["measurement_config"] is not False:
        raise ValueError("measurement-only model")
    rules = value["per_variant"][fp["variant"]]
    if any(rules[r]["status"] not in STATES for r in RULES) or type(value["retrospective"]) is not bool:
        raise ValueError("audit states")
    linked = True
    if value["retrospective"]:
        runs = value["historical_calls"]["runs"]
        matching = [r for r in runs if r.get("set", name) == name and
                    all(r.get(k) == fp[k] for k in ("model", "variant", "run_id"))]
        linked = bool(matching) and all(r["status"] == "PASS" for r in matching)
    return rules, digest, linked
