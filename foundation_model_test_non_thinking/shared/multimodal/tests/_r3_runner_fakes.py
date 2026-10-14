"""Synthetic R3 captures; reuse R2 network, image, import and JSON byte checks."""

import argparse
import copy
import json
import os
import re
import sys
from pathlib import Path
from types import SimpleNamespace

from shared.multimodal.tests._runner_fakes import BASE_URL, MODEL, offline_guard, read_json

# Variable fields: temporary/repository paths, timestamp_utc, completed_at_utc,
# artifact mtimes/hashes/protocol fingerprints, XLSX ZIP metadata and file hash.
# Runtime package/platform/script hash and HF/git probes are pinned before main.
FIXTURES = Path(__file__).parent / "fixtures"
REPO = Path(__file__).resolve().parents[3]


def cli(monkeypatch, arguments):
    """Supply parser input without touching process argv."""
    original = argparse.ArgumentParser.parse_args
    monkeypatch.setattr(argparse.ArgumentParser, "parse_args", lambda self: original(self, arguments))


def prepare_local(monkeypatch, tmp_path, responses):
    """Pin external probes and capture actual SDK request kwargs."""
    offline_guard(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MODEL_TEST_BASE", str(tmp_path))
    monkeypatch.setenv("EVAL_TIMESTAMP", "r3-session")
    for key in tuple(os.environ):
        if key.startswith("SERVING_"):
            monkeypatch.delenv(key)
    from shared.multimodal.benches import common
    metadata = sys.modules[common.build_run_config.__module__]
    client = sys.modules[common.make_client.__module__]
    monkeypatch.setattr(metadata, "get_hf_dataset_revision", lambda name: "synthetic-revision")
    monkeypatch.setattr(metadata, "get_git_commit", lambda path: "synthetic-commit")
    monkeypatch.setattr(metadata, "get_eval_script_hash", lambda path: "a" * 32)
    monkeypatch.setattr(metadata, "get_package_version", lambda name: "synthetic-version")
    monkeypatch.setattr(metadata.platform, "platform", lambda: "synthetic-platform")
    calls, constructors, sleeps = [], [], []
    outcomes = iter(responses)

    def create(**kwargs):
        calls.append(copy.deepcopy(kwargs))
        value = next(outcomes)
        if isinstance(value, Exception):
            raise value
        return SimpleNamespace(model="served", system_fingerprint="fp", provider="provider",
                               choices=[SimpleNamespace(message=SimpleNamespace(content=value))])

    def constructor(**kwargs):
        constructors.append(kwargs)
        return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))

    monkeypatch.setattr(client, "OpenAI", constructor)
    monkeypatch.setattr(client.time, "sleep", sleeps.append)
    return SimpleNamespace(calls=calls, constructors=constructors, sleeps=sleeps)


def arguments(*extra):
    """Return explicit nondefault CLI parameters for image runners."""
    return ["--model", MODEL, "--base-url", BASE_URL, "--api-key", "synthetic-key",
            "--max-tokens", "37", "--temperature", "0.25", "--seed", "7",
            "--timeout", "4", "--retry-max", "2", "--retry-backoff", "0", *extra]


def capture(output, rc, state, capsys):
    """Capture emitted bytes and workbook cells as well as requests and status."""
    from openpyxl import load_workbook
    files = {}
    for path in sorted(output.rglob("*")):
        if not path.is_file() or path.name in ("call_decision.json", "dialog.json"):
            continue
        if path.suffix == ".xlsx":
            workbook = load_workbook(path)
            files[path.relative_to(output).as_posix()] = list(workbook.active.values)
            workbook.close()
        else:
            if path.suffix == ".json":
                read_json(path, sidecar=path.name == "publish.json")
            files[path.relative_to(output).as_posix()] = path.read_text(encoding="utf-8")
    std = capsys.readouterr()
    return dict(rc=rc, calls=copy.deepcopy(state.calls), constructors=state.constructors,
                sleeps=list(state.sleeps), files=files, stdout=std.out, stderr=std.err)


def assert_capture(name, captures, tmp_path):
    """Compare against pre-refactor captures while retaining JSON byte formatting."""
    text = json.dumps(captures, ensure_ascii=False, indent=2)
    text = text.replace(str(tmp_path), "<TMP>").replace(str(REPO), "<REPO>")
    text = text.replace(sys.version.split()[0], "<PYTHON>")
    text = re.sub(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:\+00:00|Z)", "<TIME>", text)
    text = re.sub(r"sha256:[a-f0-9]{16,64}", "sha256:<HASH>", text)
    # Sidecars also contain bare protocol fingerprints; script hashes are pinned.
    text = re.sub(r"(?<![a-f0-9])[a-f0-9]{16}(?![a-f0-9])", "<FINGERPRINT>", text)
    path = FIXTURES / ("r3_" + name + ".json")
    assert text + "\n" == path.read_text(encoding="utf-8")
