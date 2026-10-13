"""Primary labels; invalid intent bundles are never sorted or padded."""

from build.catalog import intent_order
from build.wording import ACTIONS
from config import ALLOWED_ACTS, VARIANTS


def inspect_turn(turn, order):
    ids = list(dict.fromkeys(f"{frame['service']}/{frame['state']['active_intent']}"
                            for frame in turn["frames"] if frame["state"]["active_intent"] != "NONE"))
    acts = {action["act"] for frame in turn["frames"] for action in frame["actions"]}
    violations = {"a": [identifier for identifier in ids if identifier not in order],
                  "b": len(ids) > 2, "c": sorted(acts - ALLOWED_ACTS)}
    bundle = None
    if not violations["a"] and not violations["b"]:
        bundle = sorted(ids, key=order.__getitem__) + ["NONE"] * (2 - len(ids))
    actions = {act: (bool(acts & {"GOODBYE", "THANK_YOU"}) if act == "CLOSE" else act in acts)
               for act in ACTIONS}
    return {"bundle": bundle, "active_ids": ids, "actions": actions, "violations": violations}


def build(dialogues, selection, catalog):
    order = intent_order(catalog)
    records = {variant: [] for variant in VARIANTS}
    facts = {}
    for item in selection:
        key, index = item["dialogue_id"], item["turn_index"]
        request_id = f"{key}#{index}"
        fact = inspect_turn(dialogues[key]["turns"][index], order)
        facts[request_id] = {**item, **fact}
        for variant in VARIANTS:
            labels = {}
            if variant == "full" and fact["bundle"] is not None:
                labels["진행중"] = list(fact["bundle"])
            # A2: an unavailable R5-invalid bundle is not assigned a made-up label.
            labels.update(fact["actions"])
            records[variant].append({"request_id": request_id, "labels": labels})
    return records, facts
