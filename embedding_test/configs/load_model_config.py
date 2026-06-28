#!/usr/bin/env python3
"""Model config loader — yaml → shell export. 참조 ../../../model_test/configs/load_model_config.py 대응.

Usage:
  source <(python configs/load_model_config.py <model_name>)
  → KEY, MODEL, MODEL_CLASS, BACKEND, BASE_URL, TRACKS env 변수 set

run_full_eval.sh 가 이 helper 로 yaml 파싱. 평가 본체(run.py)는 KEY 로 모델을 고르고,
backend/endpoint 같은 세부는 config.py 가 같은 yaml 을 직접 읽어 해석한다.
"""
import argparse
import shlex
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("ERROR: PyYAML 미설치 — `pip install pyyaml` (requirements.txt 참고)")


def load(config_name: str) -> dict:
    config_dir = Path(__file__).parent / "models"
    name = config_name if config_name.endswith(".yaml") else f"{config_name}.yaml"
    path = config_dir / name
    if not path.exists():
        available = sorted(p.stem for p in config_dir.glob("*.yaml"))
        sys.exit(f"ERROR: config 없음 {path}\n사용 가능: {available}")
    return yaml.safe_load(path.read_text())


def emit_shell(cfg: dict, config_name: str) -> None:
    q = shlex.quote
    key = str(cfg["key"])
    # 계약: 파일명 stem == key == run.py --models 값. 어긋나면 Python(config.py)이 다른
    # 파일을 읽어 셸과 불일치할 수 있으므로 즉시 실패시킨다(codex 검토 반영).
    stem = config_name[:-5] if config_name.endswith(".yaml") else config_name
    if key != stem:
        sys.exit(f"ERROR: config 파일명('{stem}')과 yaml key('{key}')가 다릅니다 — 일치시켜야 함")
    endpoint = cfg.get("endpoint") or {}
    backend = str(cfg.get("backend", "local"))
    model_id = str(endpoint.get("model_id") or cfg["model"])
    print(f"export KEY={q(key)}")
    print(f"export MODEL={q(str(cfg['model']))}")
    print(f"export MODEL_ID={q(model_id)}")  # endpoint 서버에 등록된 id(없으면 model)
    print(f"export MODEL_CLASS={q(str(cfg.get('class', 'embedding')))}")
    print(f"export BACKEND={q(backend)}")
    print(f"export BASE_URL={q(str(endpoint.get('base_url') or ''))}")
    tracks = cfg.get("tracks", [])
    print(f"export TRACKS={q(' '.join(str(t) for t in tracks))}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("config", help="모델 config 명(확장자 없이) — 예: qwen3-8b")
    args = parser.parse_args()
    emit_shell(load(args.config), args.config)
