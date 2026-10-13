"""Independent R4 source projection, using raw files only."""

from common.io import read_json


def reconstruct(dialogue_paths, schema_path, selection_path):
    selected = read_json(selection_path)["selected_turns"]
    targets = {(item["dialogue_id"], item["turn_index"]) for item in selected}
    dialogues, seen = {}, set()
    for path in dialogue_paths:
        for raw in read_json(path):
            key = raw["dialogue_id"]
            if key in seen:
                raise ValueError(f"Independent duplicate dialogue: {key}")
            seen.add(key)
            for index, turn in enumerate(raw["turns"]):
                if (key, index) in targets:
                    dialogues[f"{key}#{index}"] = [
                        {"speaker": prior["speaker"], "utterance": prior["utterance"]}
                        for prior in raw["turns"][0:index + 1]]
    catalog = []
    for service in read_json(schema_path):
        entries = []
        for intent in service["intents"]:
            entries.append({"id": service["service_name"] + "/" + intent["name"],
                            "description": intent["description"]})
        catalog.append({"service": service["service_name"], "description": service["description"],
                        "intents": entries})
    if len(dialogues) != len(selected):
        raise ValueError("Independent source projection did not find every selected request")
    return {"dialogues": dialogues, "catalog": catalog}
