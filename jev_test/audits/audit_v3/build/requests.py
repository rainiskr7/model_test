"""Construct request payloads without using annotation fields."""

from build.wording import ACTIONS, ACTION_TEMPLATE, INTENT_1, INTENT_2, NONE_DESCRIPTION
from common.request import choice, noul
from config import VARIANTS


def questions(catalog, variant):
    if variant not in VARIANTS:
        raise ValueError(f"Unknown variant: {variant}")
    result = {}
    if variant == "full":
        criteria = {item["id"]: item["description"] for service in catalog for item in service["intents"]}
        criteria["NONE"] = NONE_DESCRIPTION
        result["진행중_1"] = choice(INTENT_1, dict(criteria))
        result["진행중_2"] = choice(INTENT_2, dict(criteria))
    result.update((act, noul(ACTION_TEMPLATE.format(description=description)))
                  for act, description in ACTIONS.items())
    return result


def build(dialogues, selection, catalog):
    result = {variant: [] for variant in VARIANTS}
    fixed = {variant: questions(catalog, variant) for variant in VARIANTS}
    for item in selection:
        key, index = item["dialogue_id"], item["turn_index"]
        state = {"dialogue": [
            {"speaker": turn["speaker"], "utterance": turn["utterance"]}
            for turn in dialogues[key]["turns"][:index + 1]], "catalog": catalog}
        for variant in VARIANTS:
            result[variant].append({**item, "request_id": f"{key}#{index}",
                                    "state": state, "questions": fixed[variant]})
    return result
