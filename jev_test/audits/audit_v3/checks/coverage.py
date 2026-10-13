"""R5: preserve each original violation; no label repair."""


def check(facts):
    counts, examples = dict.fromkeys(("a", "b", "c"), 0), []
    affected = 0
    for fact in facts.values():
        violations = fact["violations"]
        failed = [key for key, value in violations.items() if value]
        for key in failed:
            counts[key] += 1
        if failed:
            affected += 1
            if len(examples) < 5:
                examples.append({"dialogue_id": fact["dialogue_id"], "turn_index": fact["turn_index"],
                                 "violations": violations, "active_ids": fact["active_ids"]})
    return {"status": "FAIL" if any(counts.values()) else "PASS", "numerator": sum(counts.values()),
            "denominator": 3 * len(facts), "unit": "violated (turn, condition) checks",
            "violation_counts": counts, "affected_turns": affected, "sample_count": len(facts), "examples": examples}
