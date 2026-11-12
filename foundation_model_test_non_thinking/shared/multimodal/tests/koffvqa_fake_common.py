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
    config = {"decoding": {"temperature": 0, "max_tokens": 1024, "seed": 0},
            "timestamp_utc": "2026-10-20T00:00:00+00:00", "extra": kwargs["extra"]}
    if kwargs.get("judge_prompt_version") == "koffvqa-original-v1":
        config["judge"] = {"model": kwargs["judge_model"], "prompt_version": kwargs["judge_prompt_version"]}
    return config


def make_client(*_):
    calls = 0

    def create(**kwargs):
        nonlocal calls
        calls += 1
        if os.environ.get("REQUEST_CAPTURE"):
            with Path(os.environ["REQUEST_CAPTURE"]).open("a") as stream:
                stream.write(json.dumps(kwargs, ensure_ascii=False) + "\n")
        partial = os.environ.get("JUDGE_OUTCOME") == "partial" and get_timestamp().endswith("_r1")
        text = "no JSON" if partial and calls == 2 else '{"score": 8, "reason": "ok"}'
        if os.environ.get("JUDGE_OUTCOME") == "original":
            text = "근거\n최종 점수: 10점 만점에 8점"
        elif os.environ.get("JUDGE_OUTCOME") == "original_partial":
            text = "근거\n최종 점수: 10점 만점에 8점" if calls == 1 else "근거만"
        return SimpleNamespace(model="served", choices=[SimpleNamespace(message=SimpleNamespace(content=text))])

    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
