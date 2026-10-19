"""원본 frame에서 독립 고정 칸·행동·ongoing_two와 R5 위반을 계산한다."""

ACTS = {"INFORM", "REQUEST", "AFFIRM", "NEGATE", "REQUEST_ALTS", "SELECT", "GOODBYE", "THANK_YOU",
        "INFORM_INTENT", "AFFIRM_INTENT", "NEGATE_INTENT"}


def inspect(turn, catalog_order):
    active, acts = set(), set()
    for frame in turn["frames"]:
        intent = frame["state"]["active_intent"]
        if intent != "NONE":
            active.add(frame["service"] + "/" + intent)
        acts.update(a["act"] for a in frame["actions"])
    violations = dict(intent=not active <= set(catalog_order), count=len(active) > 2, act=not acts <= ACTS)
    services = [i.rsplit("/", 1)[0] for i in active]
    same_service = len(services) != len(set(services))
    slots = [i for i in catalog_order if i in active] + ["NONE"] * max(0, 2-len(active))
    return active, acts, slots, violations, same_service


def gold(turn, cat, table):
    order = [i["id"] for s in cat for i in s["intents"]]
    active, acts, slots, violations, same = inspect(turn, order)
    result = {}
    for qid, (label, role, kind, _) in table.items():
        if label.startswith("ongoing_slot_"):
            value = None if violations["intent"] or violations["count"] else slots[int(label[-1])-1]
        elif label == "ongoing_two":
            value = None if violations["intent"] or violations["count"] else str(len(active) == 2).lower()
        elif label.startswith("act:"):
            target = label.split(":", 1)[1]
            value = str(bool(acts & {"GOODBYE", "THANK_YOU"}) if target == "CLOSE" else target in acts).lower()
        else:
            raise ValueError("unknown frozen label")
        result[qid] = dict(gold=value, role=role, type=kind, label=label)
    return result


def coverage(dialogues, selected, cat, variant, set_name):
    order = [i["id"] for s in cat for i in s["intents"]]
    counts = dict(intent=0, count=0, act=0, same_service=0)
    for r in selected:
        _, _, _, bad, same = inspect(dialogues[r["dialogue_id"]]["turns"][r["turn_index"]], order)
        for k in bad:
            counts[k] += int(bad[k])
        counts["same_service"] += int(same)
    fail = counts["act"] or (variant == "full" and (counts["intent"] or counts["count"]))
    status = "FAIL" if fail else "INCOMPLETE" if variant == "full" and set_name == "kosgd2" and counts["same_service"] else "PASS"
    return dict(status=status, denominator=len(selected), violations=counts)
