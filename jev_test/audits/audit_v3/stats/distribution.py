"""Frame count and non-NONE intent count are different distributions."""

from collections import Counter


def calculate(dialogues, selection, facts):
    active_counts, frame_counts, actions = Counter(), Counter(), Counter()
    second_none = invalid = 0
    for item in selection:
        key, index = item["dialogue_id"], item["turn_index"]
        fact = facts[f"{key}#{index}"]
        active_counts[len(fact["active_ids"]) ] += 1
        frame_counts[len(dialogues[key]["turns"][index]["frames"])] += 1
        if fact["bundle"] is None:
            invalid += 1
        else:
            second_none += int(fact["bundle"][1] == "NONE")
        for act, positive in fact["actions"].items():
            actions[act] += int(positive)
    return {"active_intent_counts": {str(k): active_counts[k] for k in sorted({0, 1, 2} | set(active_counts))},
            "frame_counts": {str(k): frame_counts[k] for k in sorted({1, 2} | set(frame_counts))},
            "action_positive_counts": dict(actions),
            "second_slot_none": {"status": "INCONCLUSIVE" if invalid else "OK", "numerator": second_none,
                                 "denominator": len(selection), "unavailable_bundles": invalid,
                                 "ratio": second_none / len(selection) if not invalid else None}}
