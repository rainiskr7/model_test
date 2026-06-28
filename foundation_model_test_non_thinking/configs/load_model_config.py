#!/usr/bin/env python3
"""Model config loader — yaml → shell export.

Usage:
  source <(python configs/load_model_config.py <model_name>)
  → MODEL, TOKENIZER, BASE_URL_CHAT, BASE_URL_V1, TRACKS 같은 env 변수 set

run_full_eval.sh 가 이 helper 로 yaml 파싱.
"""
import argparse
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
    return yaml.safe_load(path.read_text())


def emit_shell(cfg: dict) -> None:
    """yaml 의 값을 bash export 문으로 출력. shlex.quote 로 안전 인용.

    평가 코드가 실제로 사용하는 필드만 export:
    - MODEL: gpustack 에 등록된 모델 ID
    - TOKENIZER: lm_eval tokenizer 경로
    - MODEL_CLASS: 평가 클래스 (llm/slm/vsm/vlm)
    - BASE_URL_{CHAT,V1}: gpustack endpoint
    - TRACKS: 평가 트랙 목록 (space-separated)

    yaml 의 backend_reference 섹션은 사람용 메모라 export 안 함.
    """
    q = shlex.quote
    print(f"export MODEL={q(cfg['model'])}")
    print(f"export TOKENIZER={q(cfg['tokenizer_path'])}")
    print(f"export MODEL_CLASS={q(cfg['class'])}")
    endpoint = cfg.get("endpoint", {})
    print(f"export BASE_URL_CHAT={q(endpoint.get('chat', ''))}")
    print(f"export BASE_URL_V1={q(endpoint.get('v1', ''))}")
    tracks = cfg.get("tracks", [])
    print(f"export TRACKS={q(' '.join(tracks))}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("config", help="모델 config 명 (확장자 없이) — e.g. google_gemma_4_31B_it")
    args = parser.parse_args()
    cfg = load(args.config)
    emit_shell(cfg)
