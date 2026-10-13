"""Required in-memory error injections; no input/output files are changed."""

import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

from copy import deepcopy

from build import catalog as catalog_builder, labels as label_builder, requests as request_builder
from checks import consistency, leak, timing
from config import SCHEMA_PATH, SELECTION_PATH
from load import kosgd, selection as selection_loader
from verify import labels_independent, source_projection


def run_injections(variants, labels, independent, source):
    baseline_r4 = leak.check_variants(variants, source)
    baseline_r7 = consistency.check_variants(variants, labels, independent)
    baseline_passed = baseline_r4["status"] == baseline_r7["status"] == "PASS"
    tests = []
    for number, name, rule in (
        (1, "append_answer_to_user_utterance", "R4"),
        (2, "extend_dialogue_into_future", "R4"),
        (3, "swap_inform_request_wording_everywhere", "R7"),
        (4, "replace_intent_answer_with_none", "R7"),
        (5, "delete_label_key", "R7"),
        (6, "change_catalog_description_everywhere", "R4"),
    ):
        modified = deepcopy(variants)
        modified_labels = deepcopy(labels)
        applicable = True
        if number == 1:
            candidates = [(i, row) for i, row in enumerate(labels["full"])
                          if any(value != "NONE" for value in row["labels"].get("진행중", []))]
            if not candidates:
                applicable = False
            else:
                index, row = candidates[0]
                answer = next(value for value in row["labels"]["진행중"] if value != "NONE")
                modified["full"][index]["state"]["dialogue"][-1]["utterance"] += " " + answer
        elif number == 2:
            # Any appended future item violates the exact prefix and length.
            modified["full"][0]["state"]["dialogue"].append({"speaker": "USER", "utterance": "미래 턴"})
        elif number == 3:
            visited = set()
            for requests in modified.values():
                for request in requests:
                    questions = request["questions"]
                    if id(questions) in visited:
                        continue
                    visited.add(id(questions))
                    questions["INFORM"]["instructions"], questions["REQUEST"]["instructions"] = (
                        questions["REQUEST"]["instructions"], questions["INFORM"]["instructions"])
        elif number == 4:
            applicable = False
            for row in modified_labels["full"]:
                for index, value in enumerate(row["labels"].get("진행중", [])):
                    if value != "NONE":
                        row["labels"]["진행중"][index] = "NONE"
                        applicable = True
                        break
                if applicable:
                    break
        elif number == 5:
            del modified_labels["full"][0]["labels"]["INFORM"]
        elif number == 6:
            visited = set()
            for requests in modified.values():
                for request in requests:
                    catalog = request["state"]["catalog"]
                    if id(catalog) not in visited:
                        visited.add(id(catalog))
                        catalog[0]["intents"][0]["description"] += " 오류 주입"
        checked = (leak.check_variants(modified, source) if rule == "R4" else
                   consistency.check_variants(modified, modified_labels, independent))
        tests.append({"number": number, "name": name, "rule": rule, "injection_applicable": applicable,
                      "observed_status": checked["status"], "detected": applicable and checked["status"] == "FAIL",
                      "examples": checked["examples"]})
    return {"status": "PASS" if baseline_passed and all(t["detected"] for t in tests) else "FAIL",
            "baseline_passed": baseline_passed, "tests": tests}


def boundary_tests():
    """Focused R6 fixtures: malformed values stay in the frame denominator."""
    cases = []
    for value in ([], ["A", "B"], "A", [None]):
        dialogue = {"x": {"turns": [{"speaker": "USER", "frames": [
            {"service": "S_1", "state": {"active_intent": "A"},
             "actions": [{"act": "INFORM_INTENT", "values": value}]}]}]}}
        result = timing.check(dialogue, [{"dialogue_id": "x", "turn_index": 0}])
        cases.append(result["status"] == "FAIL" and result["numerator"] == 0 and result["denominator"] == 1)
    frame = {"service": "S_1", "state": {"active_intent": "A"},
             "actions": [{"act": "INFORM_INTENT", "values": ["A"]}]}
    frame["actions"].append(deepcopy(frame["actions"][0]))
    result = timing.check({"x": {"turns": [{"speaker": "USER", "frames": [frame]}]}}, [])
    cases.append(result["denominator"] == 1 and result["status"] == "FAIL" and result["multiple_inform_intent_actions"] == 1)
    result = timing.check({"x": {"turns": [{"speaker": "USER", "frames": []}]}}, [])
    cases.append(result["status"] == "INCONCLUSIVE" and result["ratio"] is None)
    cases.append(not consistency._valid_value("INFORM", 1))
    cases.append(not consistency._valid_value("진행중", ["NONE"]))
    return {"passed": sum(cases), "total": len(cases), "status": "PASS" if all(cases) else "FAIL"}


def main():
    dialogues, schema, paths = kosgd.load()
    selected = selection_loader.load(dialogues)
    catalog = catalog_builder.build(schema)
    variants = request_builder.build(dialogues, selected, catalog)
    labels, _ = label_builder.build(dialogues, selected, catalog)
    independent = labels_independent.calculate(paths[:-1], SCHEMA_PATH, SELECTION_PATH)
    source = source_projection.reconstruct(paths[:-1], SCHEMA_PATH, SELECTION_PATH)
    result = run_injections(variants, labels, independent, source)
    print("BASELINE: " + ("PASS" if result["baseline_passed"] else "FAIL"))
    for test in result["tests"]:
        print(f"{test['number']} {test['name']}: {test['rule']} {test['observed_status']} detected={test['detected']}")
    boundary = boundary_tests()
    print(f"BOUNDARY_TESTS: {boundary['status']} {boundary['passed']}/{boundary['total']}")
    success = result["status"] == "PASS" and boundary["status"] == "PASS"
    print(f"SELFTEST: {'PASS' if success else 'FAIL'}")
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
