"""Copied as common.py only inside C7's disposable checkout; never contacts an API."""

import json
import os
from pathlib import Path
from types import SimpleNamespace


def get_base_dir(_):
    return Path(os.environ["MODEL_TEST_BASE"])


def get_timestamp():
    return os.environ["EVAL_TIMESTAMP"]


def get_results_dir(base, model, timestamp, benchmark, **_):
    path = base / "results" / model.replace("/", "_") / timestamp / "vision/multimodal" / benchmark
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_run_config(**kwargs):
    return {"decoding": {"temperature": 0, "max_tokens": 1024, "seed": 0},
            "timestamp_utc": "2026-10-20T00:00:00+00:00", "extra": kwargs["extra"]}


def make_client(*_):
    calls = 0

    def create(**kwargs):
        nonlocal calls
        calls += 1
        partial = os.environ.get("JUDGE_OUTCOME") == "partial" and get_timestamp().endswith("_r1")
        text = "no JSON" if partial and calls == 2 else '{"score": 8, "reason": "ok"}'
        return SimpleNamespace(model="served", choices=[SimpleNamespace(message=SimpleNamespace(content=text))])

    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
