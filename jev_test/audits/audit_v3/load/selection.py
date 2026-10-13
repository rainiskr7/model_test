"""Read the existing ordered selection; never resample."""

from common.io import read_json
from config import SAMPLE_COUNT, SELECTION_PATH


def load(dialogues):
    selection = read_json(SELECTION_PATH).get("selected_turns")
    if not isinstance(selection, list) or len(selection) != SAMPLE_COUNT:
        raise ValueError("selected_turns must contain exactly 3000 items")
    seen = set()
    for item in selection:
        if not isinstance(item, dict) or set(item) != {"dialogue_id", "turn_index"}:
            raise ValueError(f"Invalid selection item: {item}")
        key, index = item["dialogue_id"], item["turn_index"]
        if not isinstance(key, str) or type(index) is not int:
            raise ValueError(f"Invalid selection types: {item}")
        if key in seen:
            raise ValueError(f"Duplicate selected dialogue_id: {key}")
        seen.add(key)
        if key not in dialogues or not 0 <= index < len(dialogues[key]["turns"]):
            raise ValueError(f"Selected turn missing/out of bounds: {item}")
        if dialogues[key]["turns"][index]["speaker"] != "USER":
            raise ValueError(f"Selected turn is not USER: {item}")
    return selection
