"""독립 원본·선정·카탈로그 재구성. jeveval을 사용하지 않는다."""

import json
import random
from pathlib import Path


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def catalog(schema):
    result, seen = [], set()
    for service in schema:
        name = service["service_name"]
        if name in seen:
            raise ValueError("duplicate schema service")
        seen.add(name)
        intents = [{"id": name + "/" + i["name"], "description": i["description"]} for i in service["intents"]]
        if len({i["id"] for i in intents}) != len(intents):
            raise ValueError("duplicate schema intent")
        result.append(dict(service=name, description=service["description"], intents=intents))
    return result


def options(cat):
    values = {i["id"]: i["description"] for s in cat for i in s["intents"]}
    values["NONE"] = '이 칸에 넣을 진행 중인 작업이 없다'
    return values


def selected_again(dialogues, old, held):
    rng, output = random.Random(20261019), []
    if held & old or not (held | old) <= dialogues.keys():
        raise ValueError("invalid held-out source")
    for did in sorted(dialogues):
        if did in old:
            continue
        users = [i for i, t in enumerate(dialogues[did]["turns"]) if t["speaker"] == "USER"]
        if users:
            index = rng.choice(users)
            if did not in held:
                output.append(dict(dialogue_id=did, turn_index=index))
    return output


def load(root, set_name):
    root = Path(root)
    paths = sorted((root / "dataset" / set_name).glob("dialogues_*.json"))
    if not paths:
        raise FileNotFoundError("source unavailable")
    rows = [d for p in paths for d in read(p)]
    dialogues = {d["dialogue_id"]: d for d in rows}
    if len(dialogues) != len(rows):
        raise ValueError("duplicate source dialogue")
    cat = catalog(read(root / "dataset" / set_name / "extended_schema.json"))
    old = read(root / "audits/kosgd_audit/audit_result.json")["selected_turns"]
    selected = old if set_name == "kosgd" else read(root / "audits/kosgd2_selection/selection.json")["selected_turns"]
    checks = dict(selection=True, lists=True, split=True)
    if len({r["dialogue_id"] for r in old}) != 3000 or len(old) != 3000:
        checks["selection"] = False
    if len(selected) != (3000 if set_name == "kosgd" else 1200):
        checks["selection"] = False
    if len({r["dialogue_id"] for r in selected}) != len(selected):
        checks["selection"] = False
    if set_name == "kosgd2":
        held = set()
        for case in read(root / "configs/t0/fixture_v1.json")["cases"]:
            ref = case.get("state_ref", {})
            if ref.get("set") in ("kosgd", "kosgd2"):
                held.add(ref["row_id"].split("#")[0])
        checks["selection"] &= selected == selected_again(dialogues, {r["dialogue_id"] for r in old}, held)
    opts = read(root / "configs/tasks/lists/catalog_intents_plus_none.json")
    checks["lists"] = (cat == read(root / "configs/tasks/lists/kosgd_catalog.json") and
                       list(opts.items()) == list(options(cat).items()))
    split = read(root / f"configs/splits/{set_name}.json")
    expected = {f"{set_name}:{r['dialogue_id']}:{r['turn_index']}" for r in selected}
    ids = [split["representative"][g] for stage in ("dev", "test") for g in split[stage]]
    checks["split"] = len(ids) == len(expected) and set(ids) == expected and split["set"] == set_name
    sources = {}
    for r in selected:
        d, i = dialogues[r["dialogue_id"]], r["turn_index"]
        if type(i) is not int or i < 0 or i >= len(d["turns"]) or d["turns"][i]["speaker"] != "USER":
            raise ValueError("invalid selected turn")
        lid = f"{set_name}:{r['dialogue_id']}:{i}"
        sources[lid] = dict(dialogue=[{k: t[k] for k in ("speaker", "utterance")} for t in d["turns"][:i+1]],
                            catalog=cat)
    return dialogues, selected, cat, sources, checks
