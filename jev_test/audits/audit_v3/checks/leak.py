"""R4: inspect actual requests against independently reconstructed sources."""

from build.wording import ACTIONS, ACTION_TEMPLATE, INTENT_1, INTENT_2, NONE_DESCRIPTION
from common.io import json_text, sha256_text


def approved_questions(catalog, variant):
    # Rebuild from the fixed wording; do not call the request builder.
    result = {}
    if variant == "full":
        choices = {}
        for service in catalog:
            for intent in service["intents"]:
                choices[intent["id"]] = intent["description"]
        choices["NONE"] = NONE_DESCRIPTION
        for key, wording in (("진행중_1", INTENT_1), ("진행중_2", INTENT_2)):
            result[key] = {"type": "choice", "instructions": wording, "criteria": dict(choices)}
    for act, description in ACTIONS.items():
        result[act] = {"type": "noul", "instructions": ACTION_TEMPLATE.format(description=description)}
    return result


def check(requests, source, variant):
    expected_questions = approved_questions(source["catalog"], variant)
    expected_catalog_bytes = json_text(source["catalog"])
    expected_question_bytes = json_text(expected_questions)
    counts = dict.fromkeys(("a", "b", "c", "d", "e", "f"), 0)
    catalog_hashes, question_hashes, examples = set(), set(), []
    failed_requests = 0
    for record in requests:
        state, questions = record.get("state"), record.get("questions")
        errors = []
        if not isinstance(state, dict):
            state = {}
        dialogue = state.get("dialogue")
        catalog_bytes, question_bytes = json_text(state.get("catalog")), json_text(questions)
        catalog_hashes.add(sha256_text(catalog_bytes))
        question_hashes.add(sha256_text(question_bytes))
        if (set(state) != {"dialogue", "catalog"} or not isinstance(dialogue, list)
                or any(not isinstance(t, dict) or set(t) != {"speaker", "utterance"} for t in dialogue)):
            errors.append("c")
        if (not isinstance(dialogue, list) or len(dialogue) != record["turn_index"] + 1
                or not dialogue or not isinstance(dialogue[-1], dict) or dialogue[-1].get("speaker") != "USER"):
            errors.append("d")
        if dialogue != source["dialogues"].get(record["request_id"]):
            errors.append("e")
        # Byte comparison additionally checks the required object/choice order.
        if catalog_bytes != expected_catalog_bytes or question_bytes != expected_question_bytes:
            errors.append("f")
        for error in errors:
            counts[error] += 1
        if errors:
            failed_requests += 1
            if len(examples) < 5:
                examples.append({"dialogue_id": record["dialogue_id"], "turn_index": record["turn_index"],
                                 "conditions": errors})
    counts["a"] = int(len(catalog_hashes) != 1)
    counts["b"] = int(len(question_hashes) != 1)
    ids = [r["request_id"] for r in requests]
    identity_ok = len(ids) == len(source["dialogues"]) and set(ids) == set(source["dialogues"])
    if not identity_ok and len(examples) < 5:
        examples.append({"dialogue_id": None, "turn_index": None, "reason": "request identity/count mismatch"})
    passed = not any(counts.values()) and identity_ok
    return {"status": "PASS" if passed else "FAIL", "numerator": sum(counts.values()) + int(not identity_ok),
            "denominator": 4 * len(requests) + 3,
            "unit": "violated checks: a/b global, c/d/e/f per request, identity global",
            "violation_counts": counts, "failed_requests": failed_requests,
            "request_count": len(requests), "request_identity_valid": identity_ok,
            "catalog_hashes": sorted(catalog_hashes), "questions_hashes": sorted(question_hashes),
            "approved_questions_sha256": sha256_text(expected_question_bytes), "examples": examples}


def check_variants(variants, source):
    results = {variant: check(requests, source, variant) for variant, requests in variants.items()}
    return {"status": "PASS" if all(r["status"] == "PASS" for r in results.values()) else "FAIL",
            "numerator": sum(r["numerator"] for r in results.values()),
            "denominator": sum(r["denominator"] for r in results.values()),
            "examples": [dict(example, variant=variant) for variant, result in results.items()
                         for example in result["examples"]][:5], "variants": results}
