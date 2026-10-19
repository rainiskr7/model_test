"""파일럿 무전송 계획과 manifest. 정식 split·정답 계산을 사용하지 않는다."""

import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from jeveval.contract.render import render_state
from jeveval.data.items.kosgd_requests import build
from jeveval.io.config import load_taskspec
from jeveval.io.hashes import sha256_file
from jeveval.io.models import load_model_config
from jeveval.io.sources.kosgd import read_prefixes
from jeveval.io.tasks import read_b1_config, read_lists
from jeveval.run.plan_calls import plan_calls
from jeveval.types import BoundQuestion, Item
from audits.kosgd2_pilot.select_pilot import digest

MODELS = ("pplx_v1_1", "b1_qwen3_8_27b")
TASK = "configs/tasks/kosgd2_full.yaml"


def plans(root, source, selection):
    root = Path(root)
    selected = selection["selected_turns"]
    if len(selected) != 200 or digest(selected) != selection["selection_sha256"]:
        raise ValueError("invalid pilot selection")
    prefixes = read_prefixes(dict(dir=str(source), dialogues_glob="dialogues_*.json"), root, selected)
    task, lists = load_taskspec(root / TASK), read_lists(root / "configs/tasks/lists")
    b1 = read_b1_config(root / "configs/tasks/b1.yaml")
    result = {}
    for model in MODELS:
        cfg = load_model_config(root / f"configs/models/{model}.yaml")
        requests = {}
        for prefix in prefixes:
            req = build(prefix, lists["kosgd_catalog"], task, lists["catalog_intents_plus_none"], model=cfg.served_name)
            qs = [BoundQuestion(q.id, q.role, q.type, q.instructions,
                  req.questions[q.id]["criteria"] if q.type == "choice" else None,
                  req.questions[q.id]["criteria"] if q.type == "noul" else None, q.label, None) for q in task.questions]
            item = Item("kosgd2_pilot", prefix.dialogue_id, str(prefix.turn_index), json.loads(req.state), qs, {}, None)
            calls = plan_calls(item, task, cfg, b1)
            if any(c.local_errors for c in calls):
                raise ValueError("invalid pilot request")
            requests[prefix.logical_id] = calls
        result[model] = requests
    return result


def manifest(root, selection, planned):
    root = Path(root)
    paths = [TASK, "configs/tasks/b1.yaml", "configs/tasks/lists/kosgd_catalog.json",
             "configs/tasks/lists/catalog_intents_plus_none.json", *[f"configs/models/{m}.yaml" for m in MODELS]]
    return dict(schema="kosgd2_pilot_manifest/1", selection_sha256=selection["selection_sha256"],
                inputs={p: sha256_file(root / p) for p in paths},
                requests={m: {lid: {p.call_id: p.request_sha256 for p in calls} for lid, calls in rows.items()}
                          for m, rows in planned.items()}, responses={})


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", default=".")
    for name in ("source", "selection", "out"):
        p.add_argument("--" + name, required=True)
    a = p.parse_args()
    try:
        selection = json.loads(Path(a.selection).read_text())
        value = manifest(a.root, selection, plans(a.root, a.source, selection))
        target = Path(a.out)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("x") as f:
            f.write(json.dumps(value, indent=1, sort_keys=True) + "\n")
        print('{"ok":true,"sent":0}')
    except Exception:
        print('{"ok":false,"error":"pilot preparation failed"}')
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
