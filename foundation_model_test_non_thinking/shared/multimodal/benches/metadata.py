"""재현성 메타데이터 + run_config 빌더 — 단일 책임 모듈.

HF revision / git commit / 패키지 버전 / 스크립트 해시 캡처 + build_run_config.
common.py 가 re-export 하므로 기존 `from common import ...` 도 그대로 동작.
"""

import os
import sys
import hashlib
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    from .paths import safe_model_name
except ImportError:  # direct script/facade import from benches/
    from paths import safe_model_name

SHARED_ROOT = Path(__file__).resolve().parents[2]
if str(SHARED_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_ROOT))
from serving.constraints import effective_decoding  # noqa: E402


def get_hf_dataset_revision(dataset_id: str) -> Optional[str]:
    """HuggingFace dataset 의 latest commit SHA. 실패 시 None."""
    try:
        from huggingface_hub import HfApi
        info = HfApi().dataset_info(dataset_id)
        return getattr(info, "sha", None)
    except Exception:
        return None


def get_git_commit(repo_dir: Path) -> Optional[str]:
    """git repo 의 HEAD commit hash. 실패 시 None."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_dir), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def get_package_version(pkg: str) -> Optional[str]:
    """설치된 Python 패키지 버전. 실패 시 None."""
    try:
        from importlib.metadata import version
        return version(pkg)
    except Exception:
        return None


def get_eval_script_hash(script_path: str, length: int = 32) -> str:
    """평가 스크립트 + 본 framework 모듈(metadata.py) 의 sha256 (앞 32 char by default).

    model_test 가 git repo 가 아니어도 작동. (모듈 분리 전엔 common.py 를 해시했으나,
    분리 후 __file__ 은 metadata.py — framework 코드 fingerprint 목적은 동일.)
    감사/논문용은 length=64 (full sha256) 권장.
    """
    h = hashlib.sha256()
    try:
        h.update(Path(script_path).read_bytes())
    except Exception:
        pass
    try:
        h.update(Path(__file__).read_bytes())
    except Exception:
        pass
    return h.hexdigest()[:length]


def resolve_dataset_revision(dataset_id: str, cli_arg: Optional[str], env_var: str) -> tuple:
    """HF dataset revision 우선순위 결정: CLI > env var > latest (HfApi 캡처).

    Returns (revision_to_use, source_label).
    revision_to_use 가 None 이면 load_dataset 에 revision 안 박음 (latest 사용).
    """
    if cli_arg:
        return cli_arg, f"cli:--revision"
    env_val = os.environ.get(env_var)
    if env_val:
        return env_val, f"env:{env_var}"
    # latest 사용 + 캡처
    sha = get_hf_dataset_revision(dataset_id)
    return sha, "latest_captured" if sha else "latest_unknown"


def build_run_config(
    *,
    benchmark: str,
    model: str,
    base_url: str,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    seed: Optional[int] = None,
    timeout: Optional[float] = None,
    retry_max: Optional[int] = None,
    retry_backoff: Optional[float] = None,
    dataset_id: Optional[str] = None,
    dataset_revision: Optional[str] = None,
    dataset_revision_source: Optional[str] = None,
    repo_dir: Optional[Path] = None,
    repo_commit: Optional[str] = None,
    eval_script_path: Optional[str] = None,
    eval_script_hash: Optional[str] = None,
    judge_model: Optional[str] = None,
    judge_prompt_version: Optional[str] = None,
    extra: Optional[dict] = None,
) -> dict:
    """평가 재현에 필요한 모든 환경 정보를 dict 로 반환.

    summary.json 의 'run_config' 필드에 그대로 박아 넣음.
    """
    if dataset_id and dataset_revision is None:
        dataset_revision = get_hf_dataset_revision(dataset_id)
        if dataset_revision_source is None:
            dataset_revision_source = "latest_captured" if dataset_revision else "latest_unknown"
    if repo_dir is not None and repo_commit is None:
        repo_commit = get_git_commit(repo_dir)
    if eval_script_path and eval_script_hash is None:
        eval_script_hash = get_eval_script_hash(eval_script_path)

    requested_decoding, applied_decoding, serving_constraints = effective_decoding(
        temperature=temperature,
        max_tokens=max_tokens,
        seed=seed,
    )
    cfg = {
        "benchmark": benchmark,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "model": {
            "name": model,
            "safe_name": safe_model_name(model),
        },
        "endpoint": {
            "base_url": base_url,
        },
        "decoding": applied_decoding,
        "decoding_requested": requested_decoding,
        "serving_constraints": serving_constraints,
        "request_policy": {
            "timeout": timeout,
            "retry_max": retry_max,
            "retry_backoff": retry_backoff,
        },
        "dataset": {
            "huggingface_id": dataset_id,
            "revision": dataset_revision,
            "revision_source": dataset_revision_source,
            "git_repo": str(repo_dir) if repo_dir else None,
            "git_commit": repo_commit,
        },
        "judge": {
            "model": judge_model,
            "prompt_version": judge_prompt_version,
        },
        "eval_framework": {
            "script_path": eval_script_path,
            "script_hash_sha256_16": eval_script_hash,
        },
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "openai_pkg": get_package_version("openai"),
            "datasets_pkg": get_package_version("datasets"),
            "pillow_pkg": get_package_version("pillow"),
            "huggingface_hub_pkg": get_package_version("huggingface_hub"),
        },
        "env_vars": {
            "MODEL_TEST_BASE": os.environ.get("MODEL_TEST_BASE"),
            "EVAL_TIMESTAMP": os.environ.get("EVAL_TIMESTAMP"),
        },
    }
    if extra:
        cfg["extra"] = extra
    return cfg


def build_resume_context(run_config: dict, *, setting: str, session: str) -> dict:
    """Build the exact KRETA checkpoint request identity from run_config."""

    decoding = run_config.get("decoding") or {}
    return {
        "model": (run_config.get("model") or {}).get("name"),
        "setting": setting,
        "base_url": (run_config.get("endpoint") or {}).get("base_url"),
        "session": session,
        "max_tokens": decoding.get("max_tokens"),
        "decoding": decoding,
        "decoding_requested": run_config.get("decoding_requested") or {},
        "serving_constraints": run_config.get("serving_constraints") or {},
    }
