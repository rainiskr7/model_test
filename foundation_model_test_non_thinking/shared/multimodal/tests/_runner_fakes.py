"""Offline main fixtures; real image encoder, metadata builder, writers and sidecar.

Variable values excluded: summary.run_config.timestamp_utc and sidecar completion
 timestamps / artifact hashes (summary contains the timestamp). Environment version,
 platform and framework hash probes are pinned, not inferred from this machine.
"""

import base64
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import sys
from types import ModuleType, SimpleNamespace

from PIL import Image
import pytest

BENCHES = Path(__file__).resolve().parents[1] / "benches"
MODEL = "test/model-a:1"
BASE_URL = "http://unused.invalid/v1/chat/completions/"
CONSTRAINTS = {
    "unsupported_sampling_params": [], "max_output_tokens": None,
    "force_skip_special_tokens": None, "removed_parameters": [],
    "skip_special_tokens": None,
}
MC_PROMPTS = [
    "첫 질문\nOptions: A: 가, B: 나, C: 다, D: 라\n\n주어진 선택지 중 해당 옵션의 문자로 바로 답하세요.",
    "둘째 질문\nOptions: A: 마, B: 바, C: 사, D: 아\n\n주어진 선택지 중 해당 옵션의 문자로 바로 답하세요.",
]


def forbidden(*args, **kwargs):
    # pytest.fail is BaseException: runners/HF metadata must not swallow this.
    pytest.fail("unexpected live network/HF call")


def offline_guard(monkeypatch):
    import requests
    import httpx

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(requests.sessions.Session, "request", forbidden)
    monkeypatch.setattr(httpx.Client, "send", forbidden)
    datasets = ModuleType("datasets")
    datasets.load_dataset = forbidden
    monkeypatch.setitem(sys.modules, "datasets", datasets)
    hub = ModuleType("huggingface_hub")
    hub.HfApi = lambda: SimpleNamespace(dataset_info=forbidden)
    monkeypatch.setitem(sys.modules, "huggingface_hub", hub)


class Dataset:
    def __init__(self, rows):
        self.rows = list(rows)
        self.column_names = list(self.rows[0]) if self.rows else []

    def __len__(self):
        return len(self.rows)

    def __iter__(self):
        return iter(self.rows)

    def __getitem__(self, key):
        return [row[key] for row in self.rows] if isinstance(key, str) else self.rows[key]

    def select(self, indexes):
        return Dataset(self.rows[index] for index in indexes)

    def filter(self, predicate):
        return Dataset(row for row in self.rows if predicate(row))


def png(color):
    buffer = io.BytesIO()
    Image.new("RGB", (2, 3), color).save(buffer, format="PNG")
    image = Image.open(io.BytesIO(buffer.getvalue()))
    image.load()
    return image


def choice_rows(*, kmm=False):
    return [
        {"index": "item-0", "category": "document", "question": "첫 질문",
         "answer": "A", "image": png("red"),
         **(dict(A="가", B="나", C="다", D="라", hint="  힌트  ", **{"l2-category": "세부"})
            if kmm else dict(choice_a="가", choice_b="나", choice_c="다", choice_d="라"))},
        {"index": "item-1", "category": "chart", "question": "둘째 질문",
         "answer": "A", "image": png("blue"),
         **(dict(A="마", B="바", C="사", D="아", hint=None)
            if kmm else dict(choice_a="마", choice_b="바", choice_c="사", choice_d="아"))},
    ]


def load_runner(monkeypatch, name):
    monkeypatch.syspath_prepend(str(BENCHES))
    spec = importlib.util.spec_from_file_location("r2_" + name, BENCHES / (name + ".py"))
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    return runner


def prepare(monkeypatch, tmp_path, runner, rows, responses, *, extra=(), defaults=False):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MODEL_TEST_BASE", str(tmp_path))
    monkeypatch.setenv("EVAL_TIMESTAMP", "r2-session")
    for key in tuple(os.environ):
        if key.startswith("SERVING_") or key in ("K_DTCBENCH_REVISION", "K_MMBENCH_REVISION", "MTVQA_REVISION"):
            monkeypatch.delenv(key)
    offline_guard(monkeypatch)
    metadata = sys.modules[runner.build_run_config.__module__]
    client_module = sys.modules[runner.make_client.__module__]
    revision_calls, loads, constructors, calls, sleeps = [], [], [], [], []

    def revision(dataset_id):
        revision_calls.append(dataset_id)
        return "synthetic-revision"

    def load(*args, **kwargs):
        loads.append((args, kwargs))
        return Dataset(rows)

    def create(**kwargs):
        calls.append(copy.deepcopy(kwargs))
        value = next(outcomes)
        if isinstance(value, Exception):
            raise value
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=value))])

    def constructor(**kwargs):
        constructors.append(kwargs)
        return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))

    outcomes = iter(responses)
    monkeypatch.setattr(runner, "load_dataset", load)
    monkeypatch.setattr(metadata, "get_hf_dataset_revision", revision)
    monkeypatch.setattr(metadata, "get_package_version", lambda name: "synthetic-version")
    monkeypatch.setattr(metadata.platform, "platform", lambda: "synthetic-platform")
    monkeypatch.setattr(metadata, "get_eval_script_hash", lambda path: "a" * 32)
    monkeypatch.setattr(client_module, "OpenAI", constructor)
    monkeypatch.setattr(client_module.time, "sleep", sleeps.append)
    name = Path(runner.__file__).stem
    argv = [runner.__file__, "--model", MODEL, "--base-url", BASE_URL, "--api-key", "synthetic-key"]
    if not defaults:
        argv += ["--max-tokens", "37", "--temperature", "0.25", "--seed", "7",
                 "--timeout", "4", "--retry-max", "2", "--retry-backoff", "0"]
    monkeypatch.setattr(sys, "argv", [*argv, *extra])
    return SimpleNamespace(
        output=tmp_path / "results/test_model_a_1/r2-session/vision/multimodal" / name,
        calls=calls, loads=loads, revision_calls=revision_calls, constructors=constructors, sleeps=sleeps,
    )


def assert_requests(state, prompts, colors, *, defaults=False):
    assert state.constructors == [{"base_url": "http://unused.invalid/v1", "api_key": "synthetic-key"}]
    assert len(state.calls) == len(prompts)
    for call, prompt, color in zip(state.calls, prompts, colors):
        messages = call["messages"]
        url = messages[0]["content"][1]["image_url"]["url"]
        assert url.startswith("data:image/png;base64,")
        raw = base64.b64decode(url.partition(",")[2], validate=True)
        assert raw.startswith(b"\x89PNG\r\n\x1a\n")
        image = Image.open(io.BytesIO(raw))
        assert (image.format, image.mode, image.size) == ("PNG", "RGB", (2, 3))
        assert list(image.getdata()) == [color] * 6
        expected = {
            "model": MODEL, "messages": [{"role": "user", "content": [
                {"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": url}},
            ]}], "max_tokens": 512 if defaults else 37,
            "temperature": 0.0 if defaults else 0.25, "timeout": 60.0 if defaults else 4.0,
        }
        if not defaults:
            expected["seed"] = 7
        assert call == expected


def read_json(path, *, sidecar=False):
    raw = path.read_bytes()
    value = json.loads(raw)
    expected = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=sidecar) + ("\n" if sidecar else "")
    assert raw == expected.encode("utf-8")
    return value


def assert_storage(state, runner, tmp_path, *, benchmark, dataset_id, split, extra,
                   expected_count, error=False, defaults=False, load_extra=None):
    assert state.loads == [((dataset_id,), {"split": split, "revision": "synthetic-revision", **(load_extra or {})})]
    assert state.revision_calls == [dataset_id]
    assert {p.relative_to(state.output).as_posix() for p in state.output.rglob("*") if p.is_file()} == {
        "results.json", "summary.json", "_derived/publish.json", "_derived/.publish.json.lock",
    }  # no standalone run_config.json in these native runners.
    assert (state.output / "_derived/.publish.json.lock").read_bytes() == b""
    records = read_json(state.output / "results.json")
    summary = read_json(state.output / "summary.json")
    config = summary.pop("run_config")
    assert isinstance(config.pop("timestamp_utc"), str)
    decoding = {"temperature": 0.0 if defaults else 0.25, "max_tokens": 512 if defaults else 37,
                "seed": None if defaults else 7}
    assert config == {
        "benchmark": benchmark, "model": {"name": MODEL, "safe_name": "test_model_a_1"},
        "endpoint": {"base_url": BASE_URL}, "decoding": decoding, "decoding_requested": decoding,
        "serving_constraints": CONSTRAINTS,
        "request_policy": {"timeout": 60.0 if defaults else 4.0, "retry_max": 3 if defaults else 2,
                           "retry_backoff": 1.0 if defaults else 0.0},
        "dataset": {"huggingface_id": dataset_id, "revision": "synthetic-revision",
                    "revision_source": "latest_captured", "git_repo": None, "git_commit": None},
        "judge": {"model": None, "prompt_version": None},
        "eval_framework": {"script_path": runner.__file__, "script_hash_sha256_16": "a" * 32},
        "environment": {"python": sys.version.split()[0], "platform": "synthetic-platform",
                        **{key: "synthetic-version" for key in ("openai_pkg", "datasets_pkg", "pillow_pkg", "huggingface_hub_pkg")}},
        "env_vars": {"MODEL_TEST_BASE": str(tmp_path), "EVAL_TIMESTAMP": "r2-session"}, "extra": extra,
    }
    failures = ([] if expected_count == 2 else [f"기대 건수 {expected_count}와 다름"])
    if error:
        failures.append("오류 응답 1건 포함")
    counts = {"attempted": 2, "measured": 1 if error else 2, "errored": int(error),
              "unresolved": 0, "correct_measured": 1}
    fraction = {"numerator": 1, "denominator": 2, "value": 0.5, "unit": "fraction"}
    expected_summary = {
        "benchmark": benchmark, "model": MODEL, "total": 2, "correct": 1, "accuracy": 0.5,
        "counts": counts, "accuracy_strict": fraction,
        "accuracy_conditional": {"numerator": 1, "denominator": 1, "value": 1.0, "unit": "fraction"} if error else fraction,
        "publish_status": {"publishable": not failures, "failures": failures},
    }
    if benchmark == "MTVQA-KR":
        expected_summary["metric"] = "normalized exact/substring match (case-insensitive)"
    else:
        expected_summary["by_category"] = {
            "chart": {"correct": 0, "total": 1, "accuracy": 0.0},
            "document": {"correct": 1, "total": 1, "accuracy": 1.0},
        }
    if benchmark == "K-MMBench":
        expected_summary["publish_expected_count"] = expected_count
    assert summary == expected_summary
    sidecar = read_json(state.output / "_derived/publish.json", sidecar=True)
    assert set(sidecar) == {
        "aggregation_allowed", "benchmark_id", "benchmark_key", "completed_at_source",
        "completed_at_utc", "counts", "failures", "metrics", "model", "model_identity",
        "protocol", "provisional", "publishable", "schema_version", "session", "source",
        "status", "variant", "warnings",
    }
    assert sidecar["model"] == MODEL
    assert sidecar["session"] == "r2-session"
    assert sidecar["completed_at_source"] == "artifact"
    assert isinstance(sidecar["completed_at_utc"], str)
    assert sidecar["counts"] == counts
    assert sidecar["status"] == ("REJECTED" if failures else "NATIVE")
    assert sidecar["publishable"] is (not failures)
    assert sidecar["failures"] == failures
    return records


def expected_choices(*, kmm=False, error=False):
    rows = [
        {"index": "item-0", "category": "document", "question": "첫 질문", "answer": "A",
         "response": "A", "predicted": "A", "correct": True, "error": None},
        {"index": "item-1", "category": "chart", "question": "둘째 질문", "answer": "A",
         "response": {"error": "synthetic timeout"} if error else "B",
         "predicted": "" if error else "B", "correct": False,
         "error": "synthetic timeout" if error else None},
    ]
    if kmm:
        rows[0]["l2_category"], rows[1]["l2_category"] = "세부", None
    return rows
