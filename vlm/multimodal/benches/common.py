"""Shared utilities for vsm/multimodal Korean benchmark runners.

OpenAI-compatible API client + image handling + result path resolution.
"""

import os
import io
import re
import sys
import json
import time
import base64
import hashlib
import argparse
import platform
import subprocess
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any

try:
    from openai import OpenAI
except ImportError as e:
    raise SystemExit("openai 패키지 미설치 — `uv pip install openai pillow datasets`") from e


def safe_model_name(model: str) -> str:
    """Normalize model name for filesystem path.

    Examples:
        Qwen/Qwen3.5-35B-A3B → Qwen_Qwen3.5_35B_A3B
        google/gemma-4-26B-A4B → google_gemma_4_26B_A4B
    """
    return model.replace("/", "_").replace("-", "_").replace(":", "_")


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
    p = base_dir / "results" / safe_model_name(model) / timestamp / category / track / bench
    p.mkdir(parents=True, exist_ok=True)
    return p


def make_client(base_url: str, api_key: Optional[str] = None) -> OpenAI:
    """OpenAI-compat 클라이언트 생성.

    base_url 정규화: 사용자가 /chat/completions 까지 입력해도 자동 제거.
    OpenAI SDK 는 base_url 을 /v1 까지로 받고 /chat/completions 자동 추가하므로,
    중복 path 방지 위해 normalize.
    """
    api_key = api_key or os.environ.get("OPENAI_API_KEY") or "EMPTY"
    base_url = base_url.rstrip("/")
    if base_url.endswith("/chat/completions"):
        base_url = base_url[: -len("/chat/completions")]
    if base_url.endswith("/completions"):
        base_url = base_url[: -len("/completions")]
    return OpenAI(base_url=base_url, api_key=api_key)


def image_to_data_url(img: Any, fmt: str = "PNG") -> str:
    """PIL Image → data URL (base64-encoded)."""
    buf = io.BytesIO()
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    img.save(buf, format=fmt)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/{fmt.lower()};base64,{b64}"


def _is_retriable(exc: Exception) -> bool:
    """429 / 5xx / timeout / connection error 만 재시도. 4xx (auth, malformed) 은 즉시 실패."""
    msg = str(exc).lower()
    name = type(exc).__name__.lower()
    # 명시적 재시도 대상
    if any(k in name for k in ("timeout", "connection", "ratelimit")):
        return True
    if any(k in msg for k in ("timeout", "rate limit", "rate_limit", "429", "500", "502", "503", "504", "connection")):
        return True
    # 명시적 비-재시도 (인증/요청 오류)
    if any(k in msg for k in ("401", "403", "404", "400", "invalid", "unauthorized")):
        return False
    # 기본은 재시도 안 함 (안전)
    return False


def chat_with_image(
    client: OpenAI,
    model: str,
    prompt: str,
    image: Any,
    max_tokens: int = 512,
    temperature: float = 0.0,
    seed: Optional[int] = None,
    timeout: Optional[float] = 60.0,
    retry_max: int = 3,
    retry_backoff: float = 1.0,
) -> str:
    """Send single text+image prompt, return response content.

    재현성·견고성:
    - seed: OpenAI seed 파라미터 (서버 지원 시 결정론적). 미설정 시 미전달.
    - 재시도 정책: 429/5xx/timeout/connection 만 지수 backoff + jitter (±20%).
      4xx (auth, invalid) 은 즉시 실패 — 재시도 무의미.
    - retry_max: 재시도 횟수 (default 3)

    실패 시 마지막 Exception raise.
    """
    import random
    data_url = image_to_data_url(image)
    messages = [{
        "role": "user",
        "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": data_url}},
        ],
    }]
    kwargs = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if seed is not None:
        kwargs["seed"] = seed
    if timeout is not None:
        kwargs["timeout"] = timeout

    for attempt in range(retry_max):
        try:
            resp = client.chat.completions.create(**kwargs)
            return resp.choices[0].message.content or ""
        except Exception as e:
            if attempt < retry_max - 1 and _is_retriable(e):
                # 지수 backoff + jitter (±20%)
                wait = retry_backoff * (2 ** attempt)
                wait *= (0.8 + 0.4 * random.random())
                time.sleep(wait)
            else:
                raise


def standard_argparser(default_endpoint: str = "http://172.16.1.81:18090/v1") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help="모델명 (OpenAI-compat 서빙되는 모델)")
    parser.add_argument("--base-url", default=default_endpoint, help=f"OpenAI-compat endpoint (default: {default_endpoint})")
    parser.add_argument("--api-key", default=None, help="API key (없으면 OPENAI_API_KEY env 또는 EMPTY)")
    parser.add_argument("--limit", type=int, default=None, help="샘플 수 제한 (디버깅용)")
    parser.add_argument("--max-tokens", type=int, default=512, help="응답 max_tokens")
    parser.add_argument("--temperature", type=float, default=0.0, help="응답 temperature (default 0.0, 결정론적)")
    # 재현성·견고성
    parser.add_argument("--seed", type=int, default=None, help="OpenAI seed (default None, 서버 지원 시 결정론적)")
    parser.add_argument("--timeout", type=float, default=60.0, help="요청 timeout 초")
    parser.add_argument("--retry-max", type=int, default=3, help="일시 오류 재시도 횟수")
    parser.add_argument("--retry-backoff", type=float, default=1.0, help="재시도 backoff 기준 초 (지수 증가)")
    parser.add_argument("--revision", type=str, default=None,
                        help="HuggingFace dataset commit SHA (강제 재현 시 사용). "
                             "미지정 시 환경변수 또는 latest. 미지정+latest 사용 시 run_config 에 캡처된 SHA 만 기록됨.")
    return parser


def save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def append_jsonl(path: Path, record: Any) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ── 메타데이터 기록 헬퍼 (재현성 보장) ──────────────────────────────

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
    """평가 스크립트 + common.py 의 sha256 (앞 32 char by default).

    model_test 가 git repo 가 아니어도 작동.
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


def normalize_text(s: str) -> str:
    """OCR 노이즈 흡수 정규화: NFKC (전각→반각) + 공백·문장부호 정리 + lower-case.

    NFKC 가 한국어/영문/숫자/전각-반각 모두 처리 (예: '１２３' → '123').
    """
    if not isinstance(s, str):
        return ""
    s = unicodedata.normalize("NFKC", s)
    # 따옴표/괄호 제거 (OCR 흔한 노이즈)
    s = re.sub(r'[\'"`「『』」\(\)\[\]<>]', '', s)
    # 하이픈류·길이 다른 dash 통일
    s = re.sub(r'[‐‑‒–—―−]', '-', s)
    # 쉼표·마침표 양쪽 공백 제거 (숫자 1,000 vs 1, 000 통합)
    s = re.sub(r'\s*([,.])\s*', r'\1', s)
    # 다중 공백 → 단일
    s = re.sub(r'\s+', ' ', s).strip()
    return s.lower()


def normalize_number(value) -> Optional[float]:
    """숫자 문자열에서 단위/쉼표/공백 제거 후 float 반환. 실패 시 None.

    예: '12,500원' → 12500.0
        '￦12,500' → 12500.0
        '5.2 kg' → 5.2
    """
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    s = unicodedata.normalize("NFKC", value).strip()
    # 숫자 + 부호 + 점 + 쉼표 만 남김
    s = re.sub(r'[^\d.,\-+]', '', s)
    s = s.replace(",", "")
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


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
        "decoding": {
            "temperature": temperature,
            "max_tokens": max_tokens,
            "seed": seed,
        },
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


# ── CLI: 셸 wrapper(KRETA, KOFFVQA, KO-VLM-Benchmark)에서 run_config.json 작성 ──
# Usage:
#   python common.py --out PATH --benchmark NAME --model M --base-url URL \
#                    [--dataset-id ID] [--repo-dir DIR] \
#                    [--temperature T] [--max-tokens N]
if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Write run_config.json for shell-based bench wrappers")
    ap.add_argument("--out", required=True, help="run_config.json 경로")
    ap.add_argument("--benchmark", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--dataset-id", default=None)
    ap.add_argument("--repo-dir", default=None)
    ap.add_argument("--temperature", type=float, default=None)
    ap.add_argument("--max-tokens", type=int, default=None)
    args = ap.parse_args()

    cfg = build_run_config(
        benchmark=args.benchmark,
        model=args.model,
        base_url=args.base_url,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        dataset_id=args.dataset_id,
        repo_dir=Path(args.repo_dir) if args.repo_dir else None,
    )
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    save_json(out_path, cfg)
    print(f"[run_config] {out_path}")
