"""R6 원본 USER frame 시점 감사. 이웃 USER는 참고 통계이며 판정에 넣지 않는다."""


def check(dialogues):
    numerator = denominator = malformed = users_total = 0
    adjacent = {name: dict(numerator=0, denominator=0, absent=0, conflict=0) for name in ("previous", "next")}
    for d in dialogues.values():
        users = [t for t in d["turns"] if t["speaker"] == "USER"]
        users_total += len(users)
        for pos, turn in enumerate(users):
            for frame in turn["frames"]:
                actions = [a for a in frame["actions"] if a["act"] == "INFORM_INTENT"]
                if not actions:
                    continue
                denominator += 1
                values = actions[0].get("values")
                valid = len(actions) == 1 and isinstance(values, list) and len(values) == 1 and isinstance(values[0], str)
                malformed += int(not valid)
                match = valid and values[0] == frame["state"]["active_intent"]
                numerator += int(match)
                for name, index in (("previous", pos-1), ("next", pos+1)):
                    b = adjacent[name]
                    states = set() if not 0 <= index < len(users) else {
                        f["state"]["active_intent"] for f in users[index]["frames"] if f["service"] == frame["service"]}
                    if not states:
                        b["absent"] += 1
                        continue
                    b["denominator"] += 1
                    b["conflict"] += int(len(states) > 1)
                    b["numerator"] += int(valid and len(states) == 1 and values[0] in states)
    for b in adjacent.values():
        b["ratio"] = b["numerator"] / b["denominator"] if b["denominator"] and not b["conflict"] else None
    return dict(status="INCOMPLETE" if not denominator else "PASS" if numerator * 100 >= denominator * 95 else "FAIL",
                numerator=numerator, denominator=denominator, malformed=malformed, user_turns_scanned=users_total,
                unit="USER turn/frame containing INFORM_INTENT", adjacent=adjacent)
