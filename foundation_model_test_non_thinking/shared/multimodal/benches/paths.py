"""파일시스템/세션/JSON IO 헬퍼 — 단일 책임 모듈.

결과 경로 명명(safe_model_name), base/timestamp 세션 해석, results 디렉토리,
JSON 저장. common.py 가 re-export 하므로 기존 `from common import ...` 도 그대로 동작.
"""

import os
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Any


def safe_model_name(model: str) -> str:
    """Normalize model name for filesystem path.

    Examples:
        Qwen/Qwen3.5-35B-A3B → Qwen_Qwen3.5_35B_A3B
        google/gemma-4-26B-A4B → google_gemma_4_26B_A4B
    """
    return model.replace("/", "_").replace("-", "_").replace(":", "_")


def results_model_dir_name(base_dir: Path, model: str) -> str:
    """Reuse the sole case-fold-equivalent model directory spelling.

    macOS commonly hides casing drift that breaks a Linux clone.  If exactly
    one existing directory matches, its on-disk spelling is authoritative.
    Multiple case-fold matches are unsafe and are rejected.
    """

    requested = safe_model_name(model)
    results_root = Path(base_dir) / "results"
    if not results_root.is_dir():
        return requested
    matches = sorted(
        entry.name for entry in results_root.iterdir()
        if entry.is_dir() and entry.name.casefold() == requested.casefold()
    )
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError(
            f"case-fold ambiguous results model directory for {requested!r}: {matches}"
        )
    return requested


def get_base_dir(script_path: str) -> Path:
    """Resolve <model_test> root.

    Priority: MODEL_TEST_BASE env > script's grandparent² (vsm/multimodal/benches/<file>).
    """
    env = os.environ.get("MODEL_TEST_BASE")
    if env:
        return Path(env).resolve()
    # benches/<file>.py → multimodal/ → vsm/ → model_test/
    return Path(script_path).resolve().parent.parent.parent.parent


def get_timestamp(base_dir: Optional[Path] = None) -> str:
    """Resolve evaluation session timestamp.

    Priority:
      1) EVAL_TIMESTAMP env var
      2) <BASE>/.eval_session 파일 (자동 세션)
      3) 새 timestamp 생성 + .eval_session 파일에 저장 (다음 호출 부터 동일 폴더)

    base_dir 미지정 시 MODEL_TEST_BASE env var 사용.
    """
    env = os.environ.get("EVAL_TIMESTAMP")
    if env:
        return env

    base = base_dir or (Path(os.environ["MODEL_TEST_BASE"]) if os.environ.get("MODEL_TEST_BASE") else None)
    if base:
        session_file = Path(base) / ".eval_session"
        if session_file.exists():
            try:
                ts = session_file.read_text().strip()
                if ts:
                    return ts
            except Exception:
                pass
        # 새 세션 생성 + 저장
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        try:
            session_file.write_text(ts)
        except Exception:
            pass
        return ts
    # base_dir 모르면 그냥 now()
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def get_results_dir(
    base_dir: Path,
    model: str,
    timestamp: str,
    bench: str,
    *,
    category: str = "vision",
    track: str = "multimodal",
) -> Path:
    """results/<safe_model>/<ts>/<category>/<track>/<bench>/

    Default: vision/multimodal (한국어 비전 벤치마크 트랙용).
    customB(B-1~B-4) 등은 track="customB" 같이 override.
    """
    p = base_dir / "results" / results_model_dir_name(base_dir, model) / timestamp / category / track / bench
    p.mkdir(parents=True, exist_ok=True)
    return p


def save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def append_jsonl(path: Path, record: Any) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
