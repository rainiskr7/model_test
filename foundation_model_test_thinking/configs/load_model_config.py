#!/usr/bin/env python3
"""Model config loader — yaml → shell export.

Usage:
  source <(python configs/load_model_config.py <model_name>)
  → MODEL, TOKENIZER, BASE_URL_CHAT, BASE_URL_V1, TRACKS 같은 env 변수 set

run_full_eval.sh 가 이 helper 로 yaml 파싱.
"""
import argparse
import os
import shlex
import sys
from pathlib import Path

import yaml


def load(config_name: str) -> dict:
    config_dir = Path(__file__).parent / "models"
    # 확장자 없이도 받음
    name = config_name if config_name.endswith(".yaml") else f"{config_name}.yaml"
    path = config_dir / name
    if not path.exists():
        available = sorted(p.stem for p in config_dir.glob("*.yaml"))
        sys.exit(f"ERROR: config 없음 {path}\n사용 가능: {available}")
    cfg = yaml.safe_load(path.read_text()) or {}
    validate_agent_native_tool_calling(cfg)
    return cfg


def validate_agent_native_tool_calling(cfg: dict) -> None:
    """agent 트랙은 native tool calling 사용 여부를 반드시 명시한다."""
    agent = cfg.get("agent") or {}
    if "agent" in (cfg.get("tracks") or []) and "native_tool_calling" not in agent:
        sys.exit(
            "ERROR: tracks에 'agent'가 있으면 "
            "agent.native_tool_calling을 true 또는 false로 명시해야 합니다."
        )


def emit_shell(cfg: dict) -> None:
    """yaml 의 값을 bash export 문으로 출력. shlex.quote 로 안전 인용.

    평가 코드가 실제로 사용하는 필드만 export:
    - MODEL: gpustack 에 등록된 모델 ID
    - TOKENIZER: lm_eval tokenizer 경로
    - MODEL_CLASS: 평가 클래스 (llm/slm/vsm/vlm)
    - BASE_URL_{CHAT,V1}: gpustack endpoint
    - TRACKS: 평가 트랙 목록 (space-separated)
    - AGENT_NATIVE_TOOL_CALLING: agent 트랙 tool calling 모드
      agent 미지정 시 unset 을 출력해 config 간 격리를 보장한다.

    yaml 의 backend_reference 섹션은 사람용 메모라 export 안 함.
    """
    override_chat, override_v1 = endpoint_overrides()
    q = shlex.quote
    print(f"export MODEL={q(cfg['model'])}")
    print(f"export TOKENIZER={q(cfg['tokenizer_path'])}")
    print(f"export MODEL_CLASS={q(cfg['class'])}")
    endpoint = cfg.get("endpoint", {})
    print(f"export BASE_URL_CHAT={q(endpoint.get('chat', ''))}")
    print(f"export BASE_URL_V1={q(endpoint.get('v1', ''))}")
    if override_chat is not None:
        print(f"export BASE_URL_CHAT={q(override_chat)}")
        print(f"export BASE_URL_V1={q(override_v1)}")
        print(
            f"[config] endpoint override: BASE_URL_CHAT={override_chat} "
            f"BASE_URL_V1={override_v1}",
            file=sys.stderr,
        )
    tracks = cfg.get("tracks", [])
    print(f"export TRACKS={q(' '.join(tracks))}")

    emit_agent(cfg.get("agent") or {})

    # thinking sampling (모델별 권장값). 모든 트랙(.py runner / lm_eval)이 THINK_* env 로 읽음.
    # yaml 에 sampling 블록이 없으면 Qwen thinking 기본값으로 fallback.
    sampling = cfg.get("sampling", {}) or {}
    print(f"export THINK_TEMPERATURE={q(str(sampling.get('temperature', 0.6)))}")
    print(f"export THINK_TOP_P={q(str(sampling.get('top_p', 0.95)))}")
    print(f"export THINK_TOP_K={q(str(sampling.get('top_k', 20)))}")
    print(f"export THINK_MAX_TOKENS={q(str(sampling.get('max_tokens', 8192)))}")
    print(f"export THINK_SEED={q(str(sampling.get('seed', 42)))}")
    print(f"export THINK_TIMEOUT={q(str(sampling.get('timeout', 600)))}")


def endpoint_overrides() -> tuple[str | None, str | None]:
    """명시적인 endpoint override pair 를 검증해 반환."""
    chat_is_set = "BASE_URL_CHAT_OVERRIDE" in os.environ
    v1_is_set = "BASE_URL_V1_OVERRIDE" in os.environ
    if chat_is_set != v1_is_set:
        sys.exit(
            "[config] ERROR: BASE_URL_CHAT_OVERRIDE and BASE_URL_V1_OVERRIDE "
            "must be set together"
        )

    if not chat_is_set:
        return None, None

    # LM_EVAL_MODE/KRETA_SETTING 식의 암묵적 보존과 달리 별도 *_OVERRIDE 를 쓴다.
    # 이전 모델의 stale endpoint 가 다음 모델 실행을 조용히 바꾸지 않게 하기 위해서다.
    return os.environ["BASE_URL_CHAT_OVERRIDE"], os.environ["BASE_URL_V1_OVERRIDE"]


def emit_agent(agent: dict) -> None:
    """agent 섹션 → AGENT_* env.

    ⚠️ 미지정 키는 export 를 생략하는 게 아니라 반드시 `unset` 을 출력한다.
       같은 셸에서 native tool calling config 를 source 한 뒤 기존 agent config 를
       source 하면, 생략만 할 경우 이전 AGENT_* 가 그대로 남아 agent 트랙
       요청 모드가 바뀌는 회귀가 발생한다. unset 으로 항상 초기화해 config 간
       격리를 보장한다.
       이 변수는 SERVING_* 와 같은 unset 규칙을 따르며, LM_EVAL_MODE/KRETA_SETTING
       과 달리 사용자 셸 override 를 보존하지 않는다. 모델별 지정은 yaml 의
       `agent:` 섹션으로 한다.
    """
    if agent.get("native_tool_calling"):
        print("export AGENT_NATIVE_TOOL_CALLING=1")
    else:
        print("unset AGENT_NATIVE_TOOL_CALLING")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("config", help="모델 config 명 (확장자 없이) — e.g. google_gemma_4_31B_it")
    args = parser.parse_args()
    cfg = load(args.config)
    emit_shell(cfg)
