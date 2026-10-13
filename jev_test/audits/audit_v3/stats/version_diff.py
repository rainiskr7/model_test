"""English label comparison, retaining unavailable comparisons explicitly."""

import re

from build.wording import ACTIONS


def _actions(turn):
    acts = {a["act"] for f in turn["frames"] for a in f["actions"]}
    return {act: bool(acts & {"GOODBYE", "THANK_YOU"}) if act == "CLOSE" else act in acts for act in ACTIONS}


def _summary(values):
    available = [value for value in values if value is not None]
    return {"status": "OK" if len(available) == len(values) else "INCONCLUSIVE",
            "numerator": sum(available), "denominator": len(values), "compared": len(available),
            "inconclusive": len(values) - len(available),
            "mismatch_rate": sum(available) / len(values) if len(available) == len(values) and values else None,
            "mismatch_rate_among_comparable": sum(available) / len(available) if available else None}


def calculate(korean, english, selection, facts):
    pairs, rows = {}, []
    counts = {"missing_dialogue": 0, "missing_turn": 0, "speaker_mismatch": 0, "frame_count_mismatch": 0}
    for item in selection:
        key, index = item["dialogue_id"], item["turn_index"]
        ko = korean[key]["turns"][index]
        en = None
        if key not in english:
            counts["missing_dialogue"] += 1
        elif index >= len(english[key]["turns"]):
            counts["missing_turn"] += 1
        else:
            en = english[key]["turns"][index]
            counts["speaker_mismatch"] += int(ko["speaker"] != en["speaker"])
            counts["frame_count_mismatch"] += int(len(ko["frames"]) != len(en["frames"]))
            if len(ko["frames"]) == len(en["frames"]):
                for left, right in zip(ko["frames"], en["frames"]):
                    pair = left["service"], right["service"]
                    pairs[pair] = pairs.get(pair, 0) + 1
        rows.append((item, ko, en))
    forward, reverse = {}, {}
    suffix_ok = True
    for left, right in pairs:
        forward.setdefault(left, set()).add(right)
        reverse.setdefault(right, set()).add(left)
        ls, rs = re.search(r"_([0-9]+)$", left), re.search(r"_([0-9]+)$", right)
        suffix_ok = suffix_ok and bool(ls and rs and ls.group(1) == rs.group(1))
    bijective = bool(pairs) and all(len(v) == 1 for v in forward.values()) and all(len(v) == 1 for v in reverse.values())
    mapping_valid = bijective and suffix_ok
    translation = {key: next(iter(value)) for key, value in reverse.items()} if mapping_valid else {}
    fields = {"진행중": [], **{act: [] for act in ACTIONS}}
    success = {"full": [], "actions_only": []}
    detail = []
    success_acts = list(ACTIONS)[:8]
    for item, ko, en in rows:
        request_id = f"{item['dialogue_id']}#{item['turn_index']}"
        differences = dict.fromkeys(fields, None)
        aligned = en is not None and ko["speaker"] == en["speaker"]
        if aligned:
            left_actions, right_actions = _actions(ko), _actions(en)
            differences.update({act: left_actions[act] != right_actions[act] for act in ACTIONS})
            bundle = facts[request_id]["bundle"]
            if mapping_valid and len(ko["frames"]) == len(en["frames"]) and bundle is not None:
                active = {translation[f["service"]] + "/" + f["state"]["active_intent"]
                          for f in en["frames"] if f["state"]["active_intent"] != "NONE"}
                if len(active) <= 2:
                    english_bundle = sorted(active) + ["NONE"] * (2 - len(active))
                    differences["진행중"] = sorted(bundle) != sorted(english_bundle)
        for field, value in differences.items():
            fields[field].append(value)
        for variant in success:
            values = [differences[act] for act in success_acts]
            if variant == "full":
                values.append(differences["진행중"])
            # A definite behavioral mismatch already establishes the union,
            # even when the intent comparison itself is unavailable.
            success[variant].append(True if any(v is True for v in values)
                                    else None if any(v is None for v in values) else False)
        if any(value is not False for value in differences.values()) and len(detail) < 5:
            detail.append({**item, "differences": differences})
    return {"alignment": counts, "sample_count": len(selection), "mapping_bijective": bijective,
            "mapping_suffix_valid": suffix_ok, "mapping_valid": mapping_valid,
            "service_mapping": [{"ko": left, "en": right, "observations": count}
                                for (left, right), count in sorted(pairs.items())],
            "questions": {field: _summary(values) for field, values in fields.items()},
            "success_any_mismatch": {variant: _summary(values) for variant, values in success.items()},
            "examples": detail}
