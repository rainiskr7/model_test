"""R7 compares identities, payload-associated keys/types, independent labels and wording."""

from verify.labels_independent import wording_errors


def _index(records):
    index, duplicates = {}, []
    for record in records:
        key = record.get("request_id")
        if not isinstance(key, str) or key in index:
            duplicates.append(key)
        index[key] = record
    return index, duplicates


def _valid_value(key, value):
    if key == "진행중":
        return isinstance(value, list) and len(value) == 2 and all(isinstance(v, str) for v in value)
    return type(value) is bool


def check(requests, built, independent, variant):
    actual, duplicate_labels = _index(built)
    expected, duplicate_expected = _index(independent)
    request_index, duplicate_requests = _index(requests)
    errors, examples = [], []
    if duplicate_labels or duplicate_expected or duplicate_requests:
        errors.append("duplicate_or_invalid_request_id")
    if (set(actual) != set(expected) or set(request_index) != set(expected)
            or len(requests) != len(built) or len(built) != len(independent)):
        errors.append("request_id_set_or_count")
    per_request_failures = 0
    for record in requests:
        key, reasons = record["request_id"], []
        if key != f"{record['dialogue_id']}#{record['turn_index']}":
            reasons.append("request_id_metadata")
        labels = actual.get(key, {}).get("labels")
        reference = expected.get(key, {}).get("labels")
        questions = record.get("questions", {})
        if not isinstance(questions, dict):
            questions = {}
            reasons.append("questions_type")
        required = set(questions)
        if variant == "full":
            if not {"진행중_1", "진행중_2"}.issubset(required):
                reasons.append("missing_intent_questions")
            required.difference_update({"진행중_1", "진행중_2"})
            required.add("진행중")
        for name, candidate in (("build", labels), ("independent", reference)):
            if not isinstance(candidate, dict) or set(candidate) != required:
                reasons.append(name + "_label_keys")
            if isinstance(candidate, dict) and any(not _valid_value(qid, value) for qid, value in candidate.items()):
                reasons.append(name + "_value_type")
        if not reasons and isinstance(labels, dict) and isinstance(reference, dict):
            for qid in required:
                equal = (sorted(labels[qid]) == sorted(reference[qid]) if qid == "진행중"
                         else labels[qid] == reference[qid])
                if not equal:
                    reasons.append("value:" + qid)
        bad_wording = wording_errors(questions)
        if bad_wording:
            reasons.append("wording:" + ",".join(bad_wording))
        if reasons:
            per_request_failures += 1
            if len(examples) < 5:
                examples.append({"dialogue_id": record["dialogue_id"], "turn_index": record["turn_index"],
                                 "reasons": reasons})
    if errors and len(examples) < 5:
        examples.append({"dialogue_id": None, "turn_index": None, "reasons": errors})
    count = per_request_failures + len(errors)
    return {"status": "FAIL" if count else "PASS", "numerator": count,
            "denominator": len(requests) + 2, "unit": "failed requests plus global identity checks",
            "request_count": len(requests), "global_errors": errors, "examples": examples}


def check_variants(variants, labels, independent):
    results = {variant: check(requests, labels[variant], independent[variant], variant)
               for variant, requests in variants.items()}
    return {"status": "PASS" if all(r["status"] == "PASS" for r in results.values()) else "FAIL",
            "numerator": sum(r["numerator"] for r in results.values()),
            "denominator": sum(r["denominator"] for r in results.values()),
            "examples": [dict(e, variant=v) for v, r in results.items() for e in r["examples"]][:5],
            "variants": results}


def include_injection_gate(result, injections):
    # PLAN §7-1 takes precedence over SPEC §8's "not PASS evidence" wording.
    failed = [test for test in injections["tests"] if not test["detected"]]
    result["injection_tests"] = injections
    result["numerator"] += len(failed) + int(not injections["baseline_passed"])
    result["denominator"] += len(injections["tests"]) + 1
    if failed or not injections["baseline_passed"]:
        result["status"] = "FAIL"
        for test in failed:
            if len(result["examples"]) < 5:
                result["examples"].append({"dialogue_id": None, "turn_index": None,
                                           "reason": "undetected injected error", "test": test["name"]})
    return result
