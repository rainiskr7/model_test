"""Copy the immediately previous USER, including an explicit first-USER baseline."""

from build.catalog import intent_order
from build.labels import inspect_turn


def calculate(dialogues, selection, catalog, facts):
    order = intent_order(catalog)
    correct = changed = first = with_previous = changed_with_previous = unavailable = frame_missing = 0
    for item in selection:
        key, index = item["dialogue_id"], item["turn_index"]
        previous = next((turn for turn in reversed(dialogues[key]["turns"][:index]) if turn["speaker"] == "USER"), None)
        current = facts[f"{key}#{index}"]["bundle"]
        if previous is None:
            first += 1
            copied = ["NONE", "NONE"]
        else:
            with_previous += 1
            copied = inspect_turn(previous, order)["bundle"]
            prior_services = {f["service"] for f in previous["frames"] if f["state"]["active_intent"] != "NONE"}
            current_services = {f["service"] for f in dialogues[key]["turns"][index]["frames"]}
            frame_missing += int(bool(prior_services - current_services))
        if copied is None or current is None:
            unavailable += 1
            continue
        equal = sorted(copied) == sorted(current)
        correct += int(equal)
        changed += int(not equal)
        changed_with_previous += int(previous is not None and not equal)
    # SPEC-AMBIGUOUS: A3; partial counts are diagnostic, not a complete accuracy.
    return {"status": "INCONCLUSIVE" if unavailable else "OK", "numerator": correct,
            "denominator": len(selection), "accuracy": correct / len(selection) if not unavailable else None,
            "unavailable_bundles": unavailable, "first_user_count": first,
            "changed_including_first": {"numerator": changed, "denominator": len(selection),
                                        "ratio": changed / len(selection) if not unavailable else None},
            "changed_with_previous": {"numerator": changed_with_previous, "denominator": with_previous,
                                      "ratio": changed_with_previous / with_previous if with_previous and not unavailable else None},
            "frame_missing": {"numerator": frame_missing, "denominator": len(selection),
                              "ratio": frame_missing / len(selection)}}
