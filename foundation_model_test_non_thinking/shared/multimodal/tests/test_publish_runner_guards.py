from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from shared.multimodal.benches._schema import (
    detect_and_validate,
    diagnostic_warnings,
    publish_status_error,
)
from shared.multimodal.benches.metadata import build_run_config, build_resume_context
from shared.multimodal.benches.paths import get_results_dir
from shared.multimodal.publish.adapters import _add_decoding
from shared.multimodal.publish.derive import _git_index_case_map, _relative
from shared.multimodal.publish.schema import protocol_fingerprint


REPO = Path(__file__).resolve().parents[3]


def test_low_accuracy_is_diagnostic_only_but_publish_rejection_is_fatal():
    measured = {
        "benchmark": "synthetic", "model": "weak", "total": 240,
        "correct": 0, "accuracy": 0.0,
        "publish_status": {"publishable": True, "failures": []},
    }
    assert detect_and_validate(measured)[1] is None
    assert diagnostic_warnings(measured)
    assert publish_status_error(measured) is None

    measured["publish_status"] = {"publishable": False, "failures": ["오류 응답 1건 포함"]}
    assert publish_status_error(measured) is not None
    unscored = {"publish_status": {"publishable": False, "failures": ["채점 산출물 없음"]}}
    assert publish_status_error(unscored, allow_clean_unscored=True) is None


def test_run_all_accumulates_runner_failure_and_exits_nonzero(tmp_path):
    script_dir = tmp_path / "shared/multimodal"
    script_dir.mkdir(parents=True)
    shutil.copy2(REPO / "shared/multimodal/run_all.sh", script_dir / "run_all.sh")
    wrappers = [
        "run_k_dtcbench.sh", "run_koffvqa.sh", "run_mtvqa_kr.sh",
        "run_k_mmbench.sh", "run_kreta.sh", "run_b4_latency_profile.sh",
        "run_ko_vlm_benchmark.sh",
    ]
    marker = tmp_path / "continued"
    for name in wrappers:
        body = "#!/bin/bash\n"
        if name == "run_k_dtcbench.sh":
            body += "exit 7\n"
        else:
            body += f"echo {name} >> '{marker}'\nexit 0\n"
        path = script_dir / name
        path.write_text(body, encoding="utf-8")
        path.chmod(0o755)
    result = subprocess.run(
        ["bash", str(script_dir / "run_all.sh"), "model", "http://unused"],
        env={**os.environ, "EVAL_TIMESTAMP": "synthetic-session"},
        text=True, capture_output=True, check=False,
    )
    assert result.returncode == 1
    assert "K-DTCBench 실패 — 계속" in result.stdout
    assert "run_b4_latency_profile.sh" in marker.read_text(encoding="utf-8")


def test_kreta_patch_remains_well_formed():
    result = subprocess.run(
        ["git", "apply", "--numstat", "shared/multimodal/patches/kreta_infer_gpt.patch"],
        cwd=REPO, text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stderr


def test_kreta_resume_rejects_stale_session_before_inference(tmp_path):
    output = tmp_path / "data/KRETA/eval/output"
    output.mkdir(parents=True)
    (output / "model_direct.jsonl").write_text("{}\n", encoding="utf-8")
    (output / ".resume_context.json").write_text(json.dumps({
        "model": "model", "setting": "direct", "base_url": "http://old",
        "session": "old-session", "max_tokens": 32,
    }), encoding="utf-8")
    result = subprocess.run(
        ["bash", str(REPO / "shared/multimodal/run_kreta_resume.sh"),
         "model", "direct", "http://new"],
        env={
            **os.environ,
            "PATH": f"{REPO / '.venv/bin'}:{os.environ.get('PATH', '')}",
            "MODEL_TEST_BASE": str(tmp_path),
            "EVAL_TIMESTAMP": "new-session",
            "KRETA_MAX_TOKENS": "32",
        },
        text=True, capture_output=True, check=False,
    )
    assert result.returncode == 1
    assert "현재 실행 문맥과 checkpoint가 다름" in result.stdout
    assert "남은 작업" not in result.stdout


def test_kreta_resume_rejects_changed_serving_constraints(tmp_path):
    output = tmp_path / "data/KRETA/eval/output"
    output.mkdir(parents=True)
    (output / "model_direct.jsonl").write_text("{}\n", encoding="utf-8")
    monkey_env = {
        "SERVING_FORCE_SKIP_SPECIAL_TOKENS": "false",
        "SERVING_MAX_OUTPUT_TOKENS": "16",
    }
    old_env = {key: os.environ.get(key) for key in monkey_env}
    try:
        os.environ.update(monkey_env)
        config = build_run_config(
            benchmark="KRETA", model="model", base_url="http://same",
            max_tokens=32,
        )
    finally:
        for key, value in old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    context = build_resume_context(config, setting="direct", session="same-session")
    (output / ".resume_context.json").write_text(json.dumps(context), encoding="utf-8")
    result = subprocess.run(
        ["bash", str(REPO / "shared/multimodal/run_kreta_resume.sh"),
         "model", "direct", "http://same"],
        env={
            **os.environ,
            "PATH": f"{REPO / '.venv/bin'}:{os.environ.get('PATH', '')}",
            "MODEL_TEST_BASE": str(tmp_path),
            "EVAL_TIMESTAMP": "same-session",
            "KRETA_MAX_TOKENS": "32",
            "SERVING_FORCE_SKIP_SPECIAL_TOKENS": "true",
            "SERVING_MAX_OUTPUT_TOKENS": "16",
        },
        text=True, capture_output=True, check=False,
    )
    assert result.returncode == 1
    assert "현재 실행 문맥과 checkpoint가 다름" in result.stdout


def test_run_config_records_effective_serving_decoding(monkeypatch):
    monkeypatch.setenv("SERVING_UNSUPPORTED_SAMPLING_PARAMS", "seed, temperature")
    monkeypatch.setenv("SERVING_MAX_OUTPUT_TOKENS", "128")
    monkeypatch.setenv("SERVING_FORCE_SKIP_SPECIAL_TOKENS", "false")
    config = build_run_config(
        benchmark="synthetic", model="model", base_url="http://unused",
        temperature=0.0, max_tokens=512, seed=7,
    )
    assert config["decoding_requested"] == {
        "temperature": 0.0, "max_tokens": 512, "seed": 7,
    }
    assert config["decoding"] == {
        "temperature": None, "max_tokens": 128, "seed": None,
    }
    assert config["serving_constraints"] == {
        "unsupported_sampling_params": ["seed", "temperature"],
        "max_output_tokens": 128,
        "force_skip_special_tokens": False,
        "removed_parameters": ["seed", "temperature"],
        "skip_special_tokens": False,
    }
    recorded, unknown = {}, []
    _add_decoding(config, recorded, unknown)
    assert recorded["temperature_removed"] is True
    assert recorded["seed_removed"] is True
    assert recorded["max_tokens"] == 128
    assert recorded["serving_constraints"] == config["serving_constraints"]
    first_fingerprint = protocol_fingerprint(recorded, {})
    monkeypatch.setenv("SERVING_FORCE_SKIP_SPECIAL_TOKENS", "true")
    other_config = build_run_config(
        benchmark="synthetic", model="model", base_url="http://unused",
        temperature=0.0, max_tokens=512, seed=7,
    )
    other_recorded, other_unknown = {}, []
    _add_decoding(other_config, other_recorded, other_unknown)
    assert protocol_fingerprint(other_recorded, {}) != first_fingerprint


def test_get_results_dir_reuses_unique_existing_case(tmp_path):
    existing = tmp_path / "results/google_gemma_4_26B_A4B_it"
    existing.mkdir(parents=True)
    result = get_results_dir(
        tmp_path, "google_gemma_4_26b_a4b_it", "session", "bench",
    )
    assert result.parts[-5] == "google_gemma_4_26B_A4B_it"


def test_sidecar_artifact_paths_match_git_index_casing():
    tracked = subprocess.run(
        ["git", "ls-files", "-z", "results"], cwd=REPO,
        capture_output=True, check=True,
    ).stdout.decode().split("\0")
    tracked = {path for path in tracked if path}
    by_casefold = {}
    for path in tracked:
        by_casefold.setdefault(path.casefold(), set()).add(path)
    checked = 0
    for sidecar_path in REPO.glob("results/**/_derived/*.json"):
        value = json.loads(sidecar_path.read_text(encoding="utf-8"))
        unit = str((value.get("source") or {}).get("unit") or "")
        unit_parts = Path(unit).parts
        unit_spellings = {
            Path(*Path(path).parts[:len(unit_parts)]).as_posix()
            for path in tracked
            if len(Path(path).parts) >= len(unit_parts)
            and Path(*Path(path).parts[:len(unit_parts)]).as_posix().casefold() == unit.casefold()
        }
        if unit_spellings:
            assert unit_spellings == {unit}, (
                f"git index source.unit casing mismatch: {unit} -> {sorted(unit_spellings)}"
            )
            checked += 1
        for artifact in ((value.get("source") or {}).get("artifacts") or []):
            path = artifact.get("path")
            matches = by_casefold.get(str(path).casefold(), set())
            if matches:
                assert matches == {path}, f"git index casing mismatch: {path} -> {sorted(matches)}"
                checked += 1
    assert checked > 0


def test_derive_relative_path_uses_git_index_casing(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    tracked = tmp_path / "results/Model_26B/session/results.json"
    tracked.parent.mkdir(parents=True)
    tracked.write_text("{}", encoding="utf-8")
    subprocess.run(["git", "add", "results/Model_26B/session/results.json"], cwd=tmp_path, check=True)
    _git_index_case_map.cache_clear()
    differently_cased = tmp_path / "results/model_26b/session/results.json"
    assert _relative(differently_cased, tmp_path) == "results/Model_26B/session/results.json"
