"""Pin extracted CLIs against the original run_all.sh heredocs.

The oracle is the last commit that still carried the heredocs (c15274d); HEAD no
longer has them. If that commit is unavailable (shallow clone), the equivalence
tests skip instead of failing — the functional tests below still run.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from shared.multimodal.tests.test_publish_native_runner import write_tiny_accuracy_source


REPO = Path(__file__).resolve().parents[3]
BENCHES = REPO / "shared/multimodal/benches"
HEREDOC_COMMIT = "c15274d"  # last commit whose run_all.sh still embedded the heredocs


@pytest.fixture(scope="module")
def head_heredocs():
    prefix = subprocess.run(
        ["git", "rev-parse", "--show-prefix"], cwd=REPO,
        text=True, capture_output=True, check=True,
    ).stdout.strip()
    shown = subprocess.run(
        ["git", "show", f"{HEREDOC_COMMIT}:{prefix}shared/multimodal/run_all.sh"], cwd=REPO,
        text=True, capture_output=True, check=False,
    )
    if shown.returncode != 0:
        pytest.skip(f"oracle commit {HEREDOC_COMMIT} unavailable: {shown.stderr.strip()[:120]}")
    original = shown.stdout.splitlines(keepends=True)
    bodies = {}
    # Slice line ranges delimited by the original shell call and heredoc terminator.
    # Locating the ranges keeps unrelated line insertions from moving the oracle.
    for name, marker, terminator in (
        ("b3_preflight", 'B3_PREFLIGHT_OK=$(python - ', "PY"),
        ("session_sanity", 'if ! "$PY" - "$SESSION_DIR"', "PY"),
        ("paths", 'SAFE_MODEL="$("$PY" - ', "PYEOF"),
    ):
        start = next(i for i, line in enumerate(original) if marker in line) + 1
        stop = next(i for i in range(start, len(original)) if original[i].strip() == terminator)
        bodies[name] = "".join(original[start:stop])
    return bodies


def run_python(args, *, source=None):
    result = subprocess.run(
        [sys.executable, *map(str, args)], input=source,
        cwd=REPO, capture_output=True, text=True, check=False,
    )
    return result.returncode, result.stdout, result.stderr


@pytest.mark.parametrize("missing", [False, True], ids=["complete", "missing-image"])
def test_b3_preflight_matches_head(tmp_path, head_heredocs, missing):
    manifest = tmp_path / "manifest.json"
    image = tmp_path / "이미지.png"
    manifest.write_text(json.dumps([{"image": image.name}, {}, {"image": ""}]), encoding="utf-8")
    if not missing:
        image.touch()
    args = [manifest, tmp_path]
    actual = run_python([BENCHES / "b3_preflight.py", *args])
    assert actual == run_python(["-", *args], source=head_heredocs["b3_preflight"])
    rc, stdout, stderr = actual
    assert rc == 0
    if missing:
        assert stdout == "NO\n"
        assert stderr == f"[run_all] B-3 preflight 실패: 이미지 누락\n  - {image}\n"
    else:
        assert stdout.splitlines()[-1] != "NO"
        assert stdout == "OK\n"
        assert stderr == ""


@pytest.mark.parametrize("case", ["absent", "clean", "rejected"])
def test_session_sanity_matches_head(tmp_path, head_heredocs, case):
    session = tmp_path / "results/model/session"
    if case != "absent":
        source, _ = write_tiny_accuracy_source(tmp_path)
        summary_path = source / "summary.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        # The native publication fixture omits the field required by _schema.
        summary["benchmark"] = "K-DTCBench"
        if case == "rejected":
            summary["publish_status"] = {"publishable": False, "failures": ["합성 실패"]}
        summary_path.write_text(json.dumps(summary, ensure_ascii=False), encoding="utf-8")
    args = [session, "model", BENCHES]
    actual = run_python([BENCHES / "session_sanity.py", *args])
    assert actual == run_python(["-", *args], source=head_heredocs["session_sanity"])
    rc, stdout, stderr = actual
    assert stderr == ""
    if case == "absent":
        assert rc == 0
        assert stdout == f"[sanity] WARN: session dir 없음 {session}\n"
    elif case == "clean":
        assert rc == 0
        assert stdout == "[sanity] OK — 치명적 결과 없음\n"
    else:
        assert rc == 1
        assert stdout == (
            "[sanity] 1 건의 실패 결과:\n"
            "  [publish] vision/multimodal/k_dtcbench/summary.json: "
            "publish_status.publishable=false — ['합성 실패']\n"
        )


def test_paths_inline_call_matches_head(tmp_path, head_heredocs):
    (tmp_path / "results/Model_A").mkdir(parents=True)
    script = (REPO / "shared/multimodal/run_all.sh").read_text(encoding="utf-8")
    line = next(line for line in script.splitlines() if line.startswith("SAFE_MODEL="))
    source = line.split("-c '", 1)[1].split("'", 1)[0]
    args = [BENCHES, tmp_path, "model/a"]
    actual = run_python(["-c", source, *args])
    assert actual == run_python(["-", *args], source=head_heredocs["paths"])
    assert actual == (0, "Model_A\n", "")


def test_session_sanity_legacy_fallback_matches_head(tmp_path, head_heredocs):
    session = tmp_path / "session"
    source = session / "vision/multimodal/kreta/results.json"
    source.parent.mkdir(parents=True)
    source.write_text(json.dumps({"other_model": {}, "total": 0}), encoding="utf-8")
    # No _schema in the supplied directory: preserve python-stdin import semantics.
    args = [session, "model", tmp_path / "missing-benches"]
    actual = run_python([BENCHES / "session_sanity.py", *args])
    assert actual == run_python(["-", *args], source=head_heredocs["session_sanity"])
    rc, stdout, stderr = actual
    assert rc == 1 and stderr == ""
    assert "schema module 로드 실패 (No module named '_schema') — legacy 키 검사만" in stdout
    assert "total=0" in stdout
    assert "stale model key ['other_model', 'total']" in stdout
