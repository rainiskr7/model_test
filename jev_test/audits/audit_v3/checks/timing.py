"""R6 counts (USER turn, frame), retaining malformed intent actions."""

from config import TIMING_THRESHOLD


def _neighbor():
    return {"numerator": 0, "denominator": 0, "no_neighbor_user": 0,
            "neighbor_missing_service": 0, "conflicting_service_frames": 0}


def _empty():
    return {"numerator": 0, "denominator": 0, "malformed_values": 0,
            "multiple_inform_intent_actions": 0, "invalid_observations": 0,
            "previous_user": _neighbor(), "next_user": _neighbor(), "examples": []}


def _add(bucket, dialogue_id, turn_index, frame_index, frame, actions, previous, following):
    bucket["denominator"] += 1
    malformed = any(not isinstance(a.get("values"), list) or len(a["values"]) != 1
                    or not isinstance(a["values"][0], str) for a in actions)
    multiple = len(actions) != 1
    valid = not malformed and not multiple
    value = actions[0]["values"][0] if valid else None
    bucket["malformed_values"] += int(malformed)
    bucket["multiple_inform_intent_actions"] += int(multiple)
    bucket["invalid_observations"] += int(not valid)
    match = valid and frame["state"]["active_intent"] == value
    bucket["numerator"] += int(match)
    if not match and len(bucket["examples"]) < 5:
        bucket["examples"].append({"dialogue_id": dialogue_id, "turn_index": turn_index,
                                    "frame_index": frame_index, "service": frame["service"],
                                    "active_intent": frame["state"]["active_intent"],
                                    "values": [a.get("values") for a in actions],
                                    "malformed_values": malformed, "multiple_actions": multiple})
    for field, neighbor in (("previous_user", previous), ("next_user", following)):
        counts = bucket[field]
        if neighbor is None:
            counts["no_neighbor_user"] += 1
            continue
        matching = [f for f in neighbor["frames"] if f["service"] == frame["service"]]
        if not matching:
            counts["neighbor_missing_service"] += 1
            continue
        counts["denominator"] += 1
        states = {f["state"]["active_intent"] for f in matching}
        if len(states) > 1:
            # SPEC-AMBIGUOUS: A4; do not choose an arbitrary same-service frame.
            counts["conflicting_service_frames"] += 1
        else:
            counts["numerator"] += int(valid and value in states)


def _finish(bucket):
    denominator = bucket["denominator"]
    bucket["ratio"] = bucket["numerator"] / denominator if denominator else None
    for field in ("previous_user", "next_user"):
        counts = bucket[field]
        usable = counts["denominator"] and not counts["conflicting_service_frames"]
        counts["status"] = "OK" if usable else "INCONCLUSIVE"
        counts["ratio"] = counts["numerator"] / counts["denominator"] if usable else None
    return bucket


def check(dialogues, selection):
    selected = {(item["dialogue_id"], item["turn_index"]) for item in selection}
    all_frames, sample = _empty(), _empty()
    user_count = 0
    for key, dialogue in dialogues.items():
        users = [(index, turn) for index, turn in enumerate(dialogue["turns"]) if turn["speaker"] == "USER"]
        user_count += len(users)
        for position, (index, turn) in enumerate(users):
            previous = users[position - 1][1] if position > 0 else None
            following = users[position + 1][1] if position + 1 < len(users) else None
            for frame_index, frame in enumerate(turn["frames"]):
                actions = [a for a in frame["actions"] if a["act"] == "INFORM_INTENT"]
                if not actions:
                    continue
                _add(all_frames, key, index, frame_index, frame, actions, previous, following)
                if (key, index) in selected:
                    _add(sample, key, index, frame_index, frame, actions, previous, following)
    result = _finish(all_frames)
    result["status"] = ("INCONCLUSIVE" if not result["denominator"] else
                        "PASS" if result["ratio"] >= TIMING_THRESHOLD else "FAIL")
    result["threshold"] = TIMING_THRESHOLD
    result["unit"] = "USER (turn, frame) containing INFORM_INTENT"
    result["user_turn_count"] = user_count
    result["sample"] = _finish(sample)
    result["interpretation"] = "INFORM_INTENT가 있는 frame에서 라벨이 같은 턴에 반영되는지의 일치율"
    return result
