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
