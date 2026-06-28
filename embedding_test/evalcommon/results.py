"""model_test 결과 규약 어댑터 — 결과를 참조 프로젝트와 동일한 방식으로 출력.

참조: ../../../model_test/shared/multimodal/benches/common.py (get_results_dir, build_run_config)
      ../../../model_test/CONVENTIONS.md §4·§5

레이아웃(참조 common.py:99 와 동일):
  results/<safe_model>/<timestamp>/<category>/<track>/<bench>/summary.json

- safe_model_name : '/','-',':' → '_' 만 치환(점·대소문자 보존). 참조 common.py:28.
- timestamp       : EVAL_TIMESTAMP 환경변수 > .eval_session 파일(참조와 동일 세션 메커니즘).
- run_config      : 참조 build_run_config(common.py:374) 의 표준 블록을 그대로 미러.
                    임베딩 도메인 정보(encoding/dataset)는 표준 블록을 유지한 채 extra 로 덧붙인다.

세션이 비활성(EVAL_TIMESTAMP 미설정 + .eval_session 없음)이면 write_summary() 는 None 을
반환하고 아무것도 쓰지 않는다 → 러너는 기존 동작(mteb 네이티브 출력)만 수행(하위호환).
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# 이 하니스의 category(참조의 language|vision 에 대응하는 새 카테고리)
CATEGORY = "embedding"

# 하니스 루트(.eval_session / results / logs 가 놓이는 곳) = embedding_model/eval/
HARNESS_ROOT = Path(__file__).resolve().parents[1]


def safe_model_name(name: str) -> str:
    """참조 CONVENTIONS §4 / common.py:28: '/','-',':' 만 '_' 로. 점·대소문자 보존."""
    return re.sub(r"[/:\-]", "_", name)


def session_timestamp() -> str | None:
    """현재 평가 세션 타임스탬프. EVAL_TIMESTAMP > .eval_session. 없으면 None(비활성)."""
    ts = os.environ.get("EVAL_TIMESTAMP")
    if ts:
        return ts.strip()
    sf = HARNESS_ROOT / ".eval_session"
    if sf.exists():
        text = sf.read_text().strip()
        if text:
            return text
    return None


def session_active() -> bool:
    """세션이 활성화돼 규약 레이아웃으로 결과를 써야 하는가."""
    return session_timestamp() is not None


def bench_dir(model_full_name: str, track: str, bench: str,
              *, timestamp: str | None = None) -> Path:
    """results/<safe_model>/<ts>/<category>/<track>/<bench>/ (생성 포함). 참조 common.py:99."""
    ts = timestamp or session_timestamp()
    if ts is None:
        raise RuntimeError("세션 비활성: EVAL_TIMESTAMP/.eval_session 없이 결과 경로를 만들 수 없음.")
    d = (HARNESS_ROOT / "results" / safe_model_name(model_full_name) / ts
         / CATEGORY / track / bench.replace("/", "_"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _script_hash(path: str | None) -> str | None:
    """eval_framework 재현성: 스크립트 파일 sha256 앞 16자(참조 동일)."""
    if not path:
        return None
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]
    except Exception:
        return None


def _environment() -> dict:
    """참조 environment 블록의 임베딩 도메인 버전(설치된 것만)."""
    def ver(mod: str):
        try:
            return getattr(__import__(mod), "__version__", None)
        except Exception:
            return None
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "torch": ver("torch"),
        "mteb": ver("mteb"),
        "sentence_transformers": ver("sentence_transformers"),
        "transformers": ver("transformers"),
        "numpy": ver("numpy"),
    }


def build_run_config(
    *,
    benchmark: str,
    model_full_name: str,
    base_url: str | None = None,
    seed: int | None = None,
    precision: str | None = None,
    batch_size: int | None = None,
    max_seq_length: int | None = None,
    prompt_mode: str | None = None,
    dataset_id: str | None = None,
    dataset_revision: str | None = None,
    eval_script_path: str | None = None,
    extra: dict | None = None,
) -> dict:
    """참조 build_run_config(common.py:374) 의 표준 블록을 미러.

    임베딩은 생성형이 아니라 decoding/judge 가 의미 없으므로 해당 블록은 null 유지하고,
    인코딩 설정(precision/batch/seq_len/prompt_mode)은 extra.encoding 으로 덧붙인다.
    """
    enc = {k: v for k, v in {
        "precision": precision, "batch_size": batch_size,
        "max_seq_length": max_seq_length, "prompt_mode": prompt_mode,
    }.items() if v is not None}
    merged_extra = {"encoding": enc} if enc else {}
    if extra:
        merged_extra.update(extra)

    cfg = {
        "benchmark": benchmark,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "model": {"name": model_full_name, "safe_name": safe_model_name(model_full_name)},
        "endpoint": {"base_url": base_url},
        "decoding": {"temperature": None, "max_tokens": None, "seed": seed},
        "request_policy": {"timeout": None, "retry_max": None, "retry_backoff": None},
        "dataset": {
            "huggingface_id": dataset_id, "revision": dataset_revision,
            "revision_source": None, "git_repo": None, "git_commit": None,
        },
        "judge": {"model": None, "prompt_version": None},
        "eval_framework": {
            "script_path": eval_script_path,
            "script_hash_sha256_16": _script_hash(eval_script_path),
        },
        "environment": _environment(),
        "env_vars": {
            "MODEL_TEST_BASE": os.environ.get("MODEL_TEST_BASE"),
            "EVAL_TIMESTAMP": os.environ.get("EVAL_TIMESTAMP"),
        },
    }
    if merged_extra:
        cfg["extra"] = merged_extra
    return cfg


def write_summary(
    track: str,
    bench: str,
    payload: dict,
    *,
    model_full_name: str,
    timestamp: str | None = None,
) -> Path | None:
    """표준 summary.json 1건을 규약 경로에 기록하고 경로를 반환.

    세션 비활성이면 아무것도 쓰지 않고 None 반환(하위호환 — 기존 mteb 출력만 유지).
    bench: 벤치 디렉토리명(예: 'KLUE-STS__recommended'). '/' 는 '_' 로 정규화.
    payload: 최소 benchmark/model/total + (도메인 지표) + 권장 'run_config'.
    """
    if timestamp is None and not session_active():
        return None
    d = bench_dir(model_full_name, track, bench, timestamp=timestamp)
    path = d / "summary.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    return path
