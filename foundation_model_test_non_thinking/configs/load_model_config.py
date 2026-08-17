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
    cfg = apply_serving_profile(cfg)
    validate_agent_native_tool_calling(cfg)
    return cfg


def load_serving_profile(profile_name: str) -> dict:
    """configs/serving_profiles/<name>.yaml 로드."""
    profile_dir = Path(__file__).parent / "serving_profiles"
    name = profile_name if profile_name.endswith(".yaml") else f"{profile_name}.yaml"
    path = profile_dir / name
    if not path.exists():
        available = sorted(p.stem for p in profile_dir.glob("*.yaml"))
        sys.exit(f"ERROR: serving_profile 없음 {path}\n사용 가능: {available}")
    return yaml.safe_load(path.read_text()) or {}


# skip_benches 에 쓸 수 있는 이름 = run_all.sh 에 실제로 skip 훅이 달린 벤치.
# 훅 없는 이름을 적으면 조용히 무시되어 "제외했다고 생각했는데 돌아간" 상태가
# 되므로, 여기서 즉시 실패시킨다. run_all.sh 에 훅을 추가하면 여기에도 추가할 것.
SKIPPABLE_BENCHES = frozenset({"b4_latency_profile"})


def apply_serving_profile(cfg: dict) -> dict:
    """`serving_profile:` 참조를 해석해 cfg 에 병합.

    프로파일은 vLLM diffusion 처럼 **서빙 프레임워크 수준의 공통 제약**을
    한 곳에 모아두기 위한 것이다. 모델 yaml 이 같은 7줄을 복붙하면
    한 모델만 항목을 빠뜨렸을 때 조용히 400 이 나므로 프로파일로 묶는다.

    병합 규칙 (모델 yaml 이 항상 우선):
      - serving: 키 단위로 모델 값이 프로파일 값을 덮는다
      - skip_benches: 프로파일 ∪ 모델 (중복 제거, 순서 보존)
    serving_profile 이 없으면 cfg 를 그대로 돌려준다 → 기존 모델 무영향.
    """
    cfg = dict(cfg)  # 호출자의 dict 를 in-place 로 바꾸지 않는다

    profile_name = cfg.get("serving_profile")
    if profile_name:
        profile = load_serving_profile(profile_name)

        merged_serving = dict(profile.get("serving") or {})
        merged_serving.update(cfg.get("serving") or {})
        if merged_serving:
            cfg["serving"] = merged_serving

        skip = list(profile.get("skip_benches") or [])
        for bench in cfg.get("skip_benches") or []:
            if bench not in skip:
                skip.append(bench)
        if skip:
            cfg["skip_benches"] = skip

    validate_skip_benches(cfg.get("skip_benches") or [])
    return cfg


def validate_skip_benches(skip_benches: list) -> None:
    """skip 훅이 없는 이름이면 즉시 실패.

    오타(b4_latency_profile → b4_latency)를 조용히 무시하면 제외했다고
    믿은 벤치가 그대로 돌아 잘못 비교될 숫자를 만든다. 이 메커니즘의
    목적이 그걸 막는 것이므로 실패를 크게 낸다.
    """
    unknown = [b for b in skip_benches if b not in SKIPPABLE_BENCHES]
    if unknown:
        sys.exit(
            f"ERROR: skip_benches 에 알 수 없는 이름: {unknown}\n"
            f"사용 가능: {sorted(SKIPPABLE_BENCHES)}\n"
            "(run_all.sh 에 skip 훅이 있는 벤치만 지정 가능. "
            "훅을 추가했다면 load_model_config.py 의 SKIPPABLE_BENCHES 에도 추가할 것.)"
        )


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
    - SERVING_*: 서빙 백엔드 제약 (shared/serving/constraints.py 가 소비)
    - SKIP_BENCHES: 건너뛸 벤치 목록 (multimodal/run_all.sh 가 소비)
      agent/serving/skip_benches 미지정 시 unset 을 출력해 config 간 격리를 보장한다.

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

    # 모델별 평가 모드 override (선택적).
    # 이 두 변수는 사용자 셸 override 계약을 가진다:
    #   run_harness.sh 문서화: LM_EVAL_MODE=completions 로 logprob 모드 변경 가능.
    #   run_all.sh 문서화: KRETA_SETTING=direct 로 KRETA 프롬프트 모드 변경 가능.
    # 따라서 yaml 에 없을 때 unset 하지 않는다. 예:
    #   KRETA_SETTING=direct ./run_full_eval.sh <model>
    # 를 source 단계에서 죽이면 느린 HW(GB10 등)의 운영 override 가 깨진다.
    #   lm_eval_mode : KMMLU harness 모드 (chat | completions).
    #                  thinking 모델은 completions 필수 (chat 은 <think> 오염으로 점수 붕괴).
    #   kreta_setting: KRETA 프롬프트 모드 (default | direct).
    #                  느린 HW(GB10 등)는 direct 필수.
    lm_eval_mode = cfg.get("lm_eval_mode")
    if lm_eval_mode is not None:
        print(f"export LM_EVAL_MODE={q(str(lm_eval_mode))}")
    kreta_setting = cfg.get("kreta_setting")
    if kreta_setting is not None:
        print(f"export KRETA_SETTING={q(str(kreta_setting))}")

    emit_agent(cfg.get("agent") or {})
    emit_serving(cfg.get("serving") or {})

    skip_benches = cfg.get("skip_benches") or []
    if skip_benches:
        print(f"export SKIP_BENCHES={q(' '.join(skip_benches))}")
    else:
        print("unset SKIP_BENCHES")


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


def emit_serving(serving: dict) -> None:
    """serving 섹션 → SERVING_* env.

    ⚠️ 미지정 키는 export 를 생략하는 게 아니라 반드시 `unset` 을 출력한다.
       같은 셸에서 diffusion config 를 source 한 뒤 기존 AR 모델 config 를
       source 하면, 생략만 할 경우 이전 SERVING_* 가 그대로 남아 기존 모델
       요청에서 temperature 가 제거되는 회귀가 발생한다. unset 으로 항상
       초기화해 config 간 격리를 보장한다.
    """
    q = shlex.quote

    unsupported = serving.get("unsupported_sampling_params") or []
    if unsupported:
        print(f"export SERVING_UNSUPPORTED_SAMPLING_PARAMS={q(','.join(unsupported))}")
    else:
        print("unset SERVING_UNSUPPORTED_SAMPLING_PARAMS")

    if serving.get("max_output_tokens") is not None:
        print(f"export SERVING_MAX_OUTPUT_TOKENS={q(str(serving['max_output_tokens']))}")
    else:
        print("unset SERVING_MAX_OUTPUT_TOKENS")

    if serving.get("force_skip_special_tokens") is not None:
        val = "false" if serving["force_skip_special_tokens"] is False else "true"
        print(f"export SERVING_FORCE_SKIP_SPECIAL_TOKENS={val}")
    else:
        print("unset SERVING_FORCE_SKIP_SPECIAL_TOKENS")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("config", help="모델 config 명 (확장자 없이) — e.g. google_gemma_4_31B_it")
    args = parser.parse_args()
    cfg = load(args.config)
    emit_shell(cfg)
