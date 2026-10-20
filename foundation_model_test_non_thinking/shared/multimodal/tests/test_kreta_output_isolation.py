"""KRETA 답안(checkpoint) 폴더 격리 — 실행마다 <root>/<model>/<session>/<setting>/.

2026-08-30 사고: 모든 실행이 data/KRETA/eval/output 하나를 썼고, run_kreta.sh 의 stale 정리가
다른 모델의 진행 중 checkpoint 를 지웠다. 여기 테스트는 그 삭제가 구조적으로 불가능한지,
같은 폴더의 두 번째 writer 가 아무것도 지우기 전에 거부되는지, upstream evaluate.py 가
자기 폴더만 읽는지를 러너 스크립트를 실제로 실행해 확인한다.

Codex 반박(2026-09-26)을 반영한 설계:
- 삭제 회귀 테스트는 옛 레이아웃 위치(output/<other>_default.jsonl)에도 파일을 두어
  수정 전 코드(`find ./output -maxdepth 1 -delete`)에서 실제로 FAIL 하게 한다.
- C2(채점 격리)는 stub evaluate 가 받은 폴더의 jsonl 목록으로 직접 검사한다.
- 패치는 --numstat 이 아니라 pinned 원본(index)에 `git apply --check --cached` 로 검사한다.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from shared.multimodal.benches.metadata import build_resume_context, build_run_config

REPO = Path(__file__).resolve().parents[3]
RUN = REPO / "shared/multimodal/run_kreta.sh"
RESUME = REPO / "shared/multimodal/run_kreta_resume.sh"

STUB_INFER = """\
import json, os, sys
out = os.environ.get("KRETA_OUTPUT_DIR") or "./output"
os.makedirs(out, exist_ok=True)
model, setting = sys.argv[1], sys.argv[2]
with open(os.path.join(out, f"{model}_{setting}.jsonl"), "a", encoding="utf-8") as f:
    f.write(json.dumps({"id": "new-1", "response": "A"}) + "\\n")
with open(os.environ["STUB_MARKER"], "w", encoding="utf-8") as f:
    f.write(out)
"""

STUB_EVALUATE = """\
import json, os
def check_files(input_dir):
    names = sorted(n for n in os.listdir(input_dir) if n.endswith(".jsonl"))
    with open(os.path.join(input_dir, "results.json"), "w", encoding="utf-8") as f:
        json.dump({n[:-len(".jsonl")]: {"seen": True} for n in names}, f)
"""

STUB_DERIVE = "import sys\nsys.exit(0)\n"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    """tmp 안에 KRETA 저장소 모양(eval/, infer/)과 stub 들을 만든다."""
    eval_dir = tmp_path / "data/KRETA/eval"
    (eval_dir / "infer").mkdir(parents=True)
    (eval_dir / "infer/infer_gpt.py").write_text(STUB_INFER, encoding="utf-8")
    (eval_dir / "evaluate.py").write_text(STUB_EVALUATE, encoding="utf-8")
    (tmp_path / "derive_multimodal_publish.py").write_text(STUB_DERIVE, encoding="utf-8")
    env = {
        **os.environ,
        "PATH": f"{REPO / '.venv/bin'}:{os.environ.get('PATH', '')}",
        "MODEL_TEST_BASE": str(tmp_path),
        "STUB_MARKER": str(tmp_path / "marker"),
        "KRETA_MAX_TOKENS": "32",
    }
    env.pop("KRETA_OUTPUT_ROOT", None)
    env.pop("KRETA_OUTPUT_DIR", None)
    return eval_dir / "output", env


def _run(script: Path, env: dict[str, str], *args: str, session: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(script), *args],
        env={**env, "EVAL_TIMESTAMP": session},
        text=True, capture_output=True, check=False,
    )


def test_fresh_run_never_touches_another_run_checkpoint(tmp_path):
    """C1. 옛 레이아웃(output/ 바로 아래)과 새 레이아웃(다른 모델 폴더) 둘 다 살아남아야 한다.

    수정 전 run_kreta.sh 는 `find ./output -maxdepth 1 ... -delete` 로 output/ 바로 아래 jsonl 을
    지웠다 → 이 테스트가 수정 전 코드에서 FAIL 하는 이유가 바로 그 삭제다.
    """
    output, env = _fixture(tmp_path)
    old_layout = output / "other_default.jsonl"
    new_layout = output / "other/sess-B/default/other_default.jsonl"
    old_layout.parent.mkdir(parents=True)
    new_layout.parent.mkdir(parents=True)
    old_layout.write_text('{"id": "o1", "response": "B"}\n', encoding="utf-8")
    new_layout.write_text('{"id": "o2", "response": "C"}\n', encoding="utf-8")
    (output / ".resume_context.json").write_text("{}\n", encoding="utf-8")
    before = {p: _sha(p) for p in (old_layout, new_layout, output / ".resume_context.json")}

    result = _run(RUN, env, "model", "default", "http://unused", session="sess-A")

    assert result.returncode == 0, result.stdout + result.stderr
    for path, digest in before.items():
        assert path.exists(), f"{path} 가 지워졌다"
        assert _sha(path) == digest, f"{path} 내용이 바뀌었다"
    own = output / "model/sess-A/default"
    assert (tmp_path / "marker").read_text(encoding="utf-8") == str(own)
    assert (own / ".resume_context.json").exists()


def test_evaluator_sees_only_its_own_folder(tmp_path):
    """C2. evaluate 가 받은 폴더에는 이 실행의 jsonl 하나뿐이고, 산출물은 results/ 로 복사된다."""
    output, env = _fixture(tmp_path)
    foreign = output / "other/sess-A/default/other_default.jsonl"
    foreign.parent.mkdir(parents=True)
    foreign.write_text('{"id": "o1", "response": "B"}\n', encoding="utf-8")

    result = _run(RUN, env, "model", "default", "http://unused", session="sess-A")

    assert result.returncode == 0, result.stdout + result.stderr
    own = output / "model/sess-A/default"
    results = json.loads((own / "results.json").read_text(encoding="utf-8"))
    assert set(results) == {"model_default"}
    dest = tmp_path / "results/model/sess-A/vision/multimodal/kreta"
    assert {p.name for p in dest.iterdir()} >= {"model_default.jsonl", "results.json", ".resume_context.json", "run_config.json"}
    assert not (dest / ".writer.lock").exists(), "lock 디렉터리가 결과로 복사됐다"
    assert not (own / ".writer.lock").exists(), "종료 후 lock 이 남았다"


def test_second_writer_is_refused_before_deleting_anything(tmp_path):
    output, env = _fixture(tmp_path)
    own = output / "model/sess-A/default"
    (own / ".writer.lock").mkdir(parents=True)
    (own / ".writer.lock/pid").write_text(str(os.getpid()), encoding="utf-8")  # 살아 있는 PID
    checkpoint = own / "model_default.jsonl"
    checkpoint.write_text('{"id": "k1", "response": "A"}\n', encoding="utf-8")
    digest = _sha(checkpoint)

    for script in (RUN, RESUME):
        result = _run(script, env, "model", "default", "http://unused", session="sess-A")
        assert result.returncode == 1, result.stdout
        assert "다른 실행" in result.stdout
        assert _sha(checkpoint) == digest
        assert not (tmp_path / "marker").exists(), "infer 가 실행됐다"
    assert (own / ".writer.lock/pid").read_text(encoding="utf-8") == str(os.getpid()), "남의 lock 을 지웠다"


def test_stale_lock_from_dead_process_is_taken_over(tmp_path):
    output, env = _fixture(tmp_path)
    own = output / "model/sess-A/default"
    (own / ".writer.lock").mkdir(parents=True)
    dead = subprocess.run([sys.executable, "-c", "pass"], check=True)
    (own / ".writer.lock/pid").write_text(str(dead.args and os.getpid() + 40000), encoding="utf-8")

    result = _run(RUN, env, "model", "default", "http://unused", session="sess-A")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "stale writer lock 제거" in result.stdout
    assert (tmp_path / "marker").exists()


def test_model_name_with_slash_is_rejected_before_any_write(tmp_path):
    output, env = _fixture(tmp_path)
    for bad in ("org/model", "/abs/model", "../escape", ".hidden"):
        result = _run(RUN, env, bad, "default", "http://unused", session="sess-A")
        assert result.returncode == 1, bad
        assert "'/' 나 선행 '.'" in result.stdout, bad
    assert not output.exists()
    assert not (tmp_path / "results").exists()


def _matching_context(output: Path, *, session: str, folder_session: str | None = None) -> Path:
    """러너와 같은 env 로 만든 완전 일치 context. folder_session 이 다르면 폴더만 다른 세션."""
    config = build_run_config(benchmark="KRETA", model="model", base_url="http://same", max_tokens=32)
    context = build_resume_context(config, setting="direct", session=session)
    folder = output / "model" / (folder_session or session) / "direct"
    folder.mkdir(parents=True)
    (folder / "model_direct.jsonl").write_text('{"id": "k1", "response": "A"}\n', encoding="utf-8")
    (folder / ".resume_context.json").write_text(json.dumps(context), encoding="utf-8")
    return folder


def test_resume_continues_when_context_fully_matches(tmp_path):
    output, env = _fixture(tmp_path)
    folder = _matching_context(output, session="same-session")

    result = _run(RESUME, env, "model", "direct", "http://same", session="same-session")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "RESUME: 문맥 일치 checkpoint만 보존" in result.stdout
    assert (tmp_path / "marker").read_text(encoding="utf-8") == str(folder)
    lines = (folder / "model_direct.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(l)["id"] for l in lines] == ["k1", "new-1"], "기존 행이 보존되고 새 행이 이어 붙어야 한다"


def test_resume_rejects_when_only_session_differs(tmp_path):
    """context 의 다른 7필드는 모두 같고 session 만 다르다 — session 검사 자체의 회귀 테스트."""
    output, env = _fixture(tmp_path)
    folder = _matching_context(output, session="recorded-session", folder_session="running-session")

    result = _run(RESUME, env, "model", "direct", "http://same", session="running-session")

    assert result.returncode == 1, result.stdout
    assert "현재 실행 문맥과 checkpoint가 다름" in result.stdout
    assert not (tmp_path / "marker").exists()
    assert (folder / "model_direct.jsonl").exists()


def test_resume_without_checkpoint_in_its_own_folder_fails_closed(tmp_path):
    output, env = _fixture(tmp_path)
    _matching_context(output, session="other-session")  # 다른 세션 폴더에만 있다

    result = _run(RESUME, env, "model", "direct", "http://same", session="this-session")

    assert result.returncode == 1
    assert "검증 가능한 checkpoint/context 없음" in result.stdout
    assert not (tmp_path / "marker").exists()


def test_output_root_override_keeps_per_run_subfolders(tmp_path):
    """두 레인이 같은 KRETA_OUTPUT_ROOT 를 상속해도 폴더가 합쳐지지 않는다 (Codex 반박 3)."""
    output, env = _fixture(tmp_path)
    root = tmp_path / "shared-root"
    env = {**env, "KRETA_OUTPUT_ROOT": str(root)}

    a = _run(RUN, env, "alpha", "default", "http://unused", session="sess")
    b = _run(RUN, env, "beta", "default", "http://unused", session="sess")

    assert a.returncode == 0 and b.returncode == 0, a.stdout + b.stdout
    assert (root / "alpha/sess/default/alpha_default.jsonl").exists()
    assert (root / "beta/sess/default/beta_default.jsonl").exists()
    assert not output.exists()


@pytest.mark.skipif(not (REPO / "data/KRETA/.git").exists(), reason="data/KRETA 미설치")
def test_kreta_patch_applies_to_pinned_upstream():
    """install.sh 는 checkout 후 실제 apply 를 하므로 문법 검사(--numstat)로는 부족하다.
    index 는 pinned SHA 원본을 담고 있어 --cached 가 원본 문맥 검사가 된다."""
    result = subprocess.run(
        ["git", "-C", str(REPO / "data/KRETA"), "apply", "--check", "--cached",
         str(REPO / "shared/multimodal/patches/kreta_infer_gpt.patch")],
        text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    patched = (REPO / "data/KRETA/eval/infer/infer_gpt.py").read_text(encoding="utf-8")
    assert 'os.environ.get("KRETA_OUTPUT_DIR")' in patched


@pytest.mark.skipif(not (REPO / "data/KRETA/eval/evaluate.py").exists(), reason="data/KRETA 미설치")
def test_upstream_evaluate_reads_only_the_given_folder(tmp_path):
    """러너의 `import evaluate; check_files(folder)` 호출이 __main__ 과 같은 산출물을 낸다."""
    folder = tmp_path / "m/sess/default"
    folder.mkdir(parents=True)
    rows = [
        {"id": f"x{i}", "response": "A", "A": "a", "B": "b", "C": "c", "D": "d",
         "answer": "A", "category": "none", "image_type": "t", "topic_difficulty": "System1"}
        for i in range(2577)
    ]
    (folder / "m_default.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    (tmp_path / "m/other_default.jsonl").write_text("{}\n", encoding="utf-8")  # 상위 폴더 — 읽히면 안 됨
    result = subprocess.run(
        [str(REPO / ".venv/bin/python"), "-", str(folder)],
        input='import sys\nsys.path.insert(0, ".")\nimport evaluate\nevaluate.check_files(sys.argv[1])\n',
        cwd=REPO / "data/KRETA/eval", text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    results = json.loads((folder / "results.json").read_text(encoding="utf-8"))
    assert set(results) == {"m_default"}
