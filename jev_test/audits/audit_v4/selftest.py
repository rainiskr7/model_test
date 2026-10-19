"""v3 여섯 주입과 새 일곱 주입을 합성 바이트/정답에서 지정 규칙으로 검사한다."""

from copy import deepcopy
import json

from audits.audit_v4.checks import r4, r7, hashes
from audits.audit_v4.independent.requests import wire


def fixture(set_name):
    state = dict(dialogue=[dict(speaker="USER", utterance="synthetic canary")], catalog=[
        dict(service="a", description="first", intents=[]), dict(service="b", description="second", intents=[])])
    qs = {q: dict(type="choice" if q.startswith("ongoing_") and q != "ongoing_two" else "noul",
                 instructions=q, criteria={"a": "one", "b": "two"})
          for q in ("ongoing_1", "ongoing_2", "act_inform", "act_request", "ongoing_two")}
    gold = {q: dict(gold=v, role="success", type=qs[q]["type"], label=q) for q, v in
            zip(qs, ("a", "b", "true", "false", "true"))}
    if set_name == "kosgd":
        del qs["ongoing_two"], gold["ongoing_two"]
    return {"id": dict(state=wire(state).decode(), questions=qs)}, {"id": gold}


def mutate(number, requests, labels, mapping):
    r, gold = requests["id"], labels["id"]
    state = json.loads(r["state"])
    qs = r["questions"]
    if number == 1: state["dialogue"][-1]["utterance"] += " a"
    elif number in (2, 10): state["dialogue"].append(dict(speaker="USER", utterance="future"))
    elif number == 3:
        qs["act_inform"]["instructions"], qs["act_request"]["instructions"] = qs["act_request"]["instructions"], qs["act_inform"]["instructions"]
    elif number == 4: gold["ongoing_1"]["gold"] = "NONE"
    elif number == 5: del gold["act_inform"]
    elif number == 6: state["catalog"][0]["description"] += " changed"
    elif number == 7: state["catalog"].reverse()
    elif number == 8: qs["act_inform"]["instructions"] += "x"
    elif number == 9: state["dialogue"][0]["frame"] = {}
    elif number == 11: gold["ongoing_1"]["gold"], gold["ongoing_2"]["gold"] = "b", "a"
    elif number == 12: gold["ongoing_two"]["gold"] = "false"
    elif number == 13: mapping.update(A="b", B="a")
    r["state"] = wire(state).decode()


def run(set_name="kosgd2"):
    expected, gold = fixture(set_name)
    tests = []
    rules = ("R4", "R4", "R7", "R7", "R7", "R4", "R4", "R4", "R4", "R4", "R7", "R7", "v4_hash")
    baseline = r4(expected, expected) == r7(gold, gold) == "PASS"
    for number, rule in enumerate(rules, 1):
        if number == 12 and set_name == "kosgd":
            tests.append(dict(number=number, rule=rule, status="NOT_APPLICABLE"))
            continue
        actual, labels, mapping = deepcopy(expected), deepcopy(gold), dict(A="a", B="b")
        before = wire([actual, labels, mapping])
        mutate(number, actual, labels, mapping)
        changed = before != wire([actual, labels, mapping])
        status = (r4(actual, expected) if rule == "R4" else r7(labels, gold, actual, expected) if rule == "R7" else
                  hashes(b"body", b"body", b"body", mapping, dict(A="a", B="b")))
        tests.append(dict(number=number, rule=rule, baseline_passed=baseline, changed=changed,
                          observed=status, status="PASS" if baseline and changed and status == "FAIL" else "FAIL"))
    return dict(status="PASS" if all(t["status"] in ("PASS", "NOT_APPLICABLE") for t in tests) else "FAIL", tests=tests)
