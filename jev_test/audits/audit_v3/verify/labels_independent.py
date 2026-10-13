"""Independent label calculation: only original JSON files enter this module."""

from common.io import read_json

# Deliberately independent from the primary action/wording table.
ACTION_DESCRIPTIONS = {
    "INFORM": "정보를 제공", "REQUEST": "정보를 요청",
    "AFFIRM": "동의하거나 긍정", "NEGATE": "부정하거나 거절",
    "REQUEST_ALTS": "다른 대안을 요청", "SELECT": "제시된 선택지를 선택",
    "CLOSE": "작별 인사 또는 감사 표현", "INFORM_INTENT": "원하는 작업이나 의도를 전달",
    "AFFIRM_INTENT": "제안된 작업이나 의도에 동의", "NEGATE_INTENT": "제안된 작업이나 의도를 거절",
}


def calculate(dialogue_paths, schema_path, selection_path):
    selected = read_json(selection_path)["selected_turns"]
    wanted = {}
    for item in selected:
        key, index = item["dialogue_id"], item["turn_index"]
        if key in wanted or type(index) is not int or index < 0:
            raise ValueError("Invalid independent selection")
        wanted[key] = index
    schema_ids = []
    for service in read_json(schema_path):
        for intent in service["intents"]:
            identifier = service["service_name"] + "/" + intent["name"]
            if identifier in schema_ids:
                raise ValueError("Duplicate independent schema ID")
            schema_ids.append(identifier)
    computed, seen = {}, set()
    for path in dialogue_paths:
        for dialogue in read_json(path):
            key = dialogue["dialogue_id"]
            if key in seen:
                raise ValueError(f"Duplicate independent dialogue ID: {key}")
            seen.add(key)
            if key not in wanted:
                continue
            index = wanted[key]
            turn = dialogue["turns"][index]
            if turn["speaker"] != "USER":
                raise ValueError("Independent selected turn must be USER")
            active = set()
            action_labels = dict.fromkeys(ACTION_DESCRIPTIONS, False)
            for frame in turn["frames"]:
                state = frame.get("state")
                if not isinstance(state, dict) or not isinstance(state.get("active_intent"), str):
                    raise ValueError("Independent USER active_intent missing or not a string")
                if state["active_intent"] != "NONE":
                    active.add(frame["service"] + "/" + state["active_intent"])
                for action in frame["actions"]:
                    act = action["act"]
                    if act in ("THANK_YOU", "GOODBYE"):
                        action_labels["CLOSE"] = True
                    elif act in action_labels:
                        action_labels[act] = True
            full = {}
            if len(active) <= 2 and active.issubset(schema_ids):
                ordered = [identifier for identifier in schema_ids if identifier in active]
                while len(ordered) < 2:
                    ordered.append("NONE")
                full["진행중"] = ordered
            full.update(action_labels)
            computed[f"{key}#{index}"] = {"full": full, "actions_only": action_labels}
    if len(computed) != len(selected):
        raise ValueError("Independent labels did not find all selected requests")
    return {variant: [{"request_id": f"{item['dialogue_id']}#{item['turn_index']}",
                       "labels": computed[f"{item['dialogue_id']}#{item['turn_index']}"][variant]}
                      for item in selected] for variant in ("full", "actions_only")}


def wording_errors(questions):
    errors = []
    for act, description in ACTION_DESCRIPTIONS.items():
        question = questions.get(act)
        if not isinstance(question, dict):
            errors.append(act)
            continue
        instruction = question.get("instructions")
        if (question.get("type") != "noul" or not isinstance(instruction, str)
                or description not in instruction):
            errors.append(act)
    return errors
