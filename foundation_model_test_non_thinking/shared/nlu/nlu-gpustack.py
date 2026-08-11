import requests
import json
import os
import sys
import argparse
import importlib
from datetime import datetime
from pathlib import Path
try:
    _dotenv = importlib.import_module("dotenv")
    _dotenv.load_dotenv()
except Exception:
    pass

api_key = os.getenv("OPENAI_API_KEY")

SCRIPT_DIR = Path(__file__).resolve().parent
PROMPT_DIR = SCRIPT_DIR / "prompt"
DEFAULT_ENDPOINT = "http://172.16.1.81:18090/v1/chat/completions"

# shared/ 를 import path 에 추가 (vsm/nlu 는 shared/nlu 로의 symlink 라 resolve 필요)
sys.path.insert(0, str(SCRIPT_DIR.parent))
from serving.constraints import apply as apply_serving_constraints  # noqa: E402


def get_base_dir() -> Path:
    """Resolve project root.

    Priority: MODEL_TEST_BASE env var > script's grandparent (<class>/nlu → <BASE>).
    """
    env_base = os.environ.get("MODEL_TEST_BASE")
    if env_base:
        return Path(env_base).resolve()
    return SCRIPT_DIR.parent.parent.resolve()


def get_timestamp() -> str:
    """Resolve evaluation session timestamp.

    Priority:
      1) EVAL_TIMESTAMP env var
      2) <BASE>/.eval_session 파일 (자동 세션)
      3) 새 timestamp 생성 + .eval_session 에 저장 (이후 호출 부터 동일)
    """
    env = os.environ.get("EVAL_TIMESTAMP")
    if env:
        return env
    base = get_base_dir()
    session_file = base / ".eval_session"
    if session_file.exists():
        try:
            ts = session_file.read_text().strip()
            if ts:
                return ts
        except Exception:
            pass
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    try:
        session_file.write_text(ts)
    except Exception:
        pass
    return ts


def get_response(prompt, model, endpoint: str, timeout: float = 600.0):
    """프롬프트를 입력받아 모델의 응답을 반환

    timeout: 네트워크 hang 방지용 (default 600초 = 10분)
    큰 모델 (27B dense) + max_tokens 8192 조합에서 120초로는 부족했음.
    """
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.0,        # 평가 결정론적 (codex 권장)
        "max_tokens": 8192,        # 긴 한국어 응답 안전 상한
        "top_p": None
    }
    # 서빙 백엔드 제약 적용 (SERVING_* env 미설정 시 no-op)
    apply_serving_constraints(payload)

    response = requests.post(
        url=endpoint,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-Title": "NLU Evaluation",
        },
        data=json.dumps(payload),
        timeout=timeout,
    )

    response.raise_for_status()
    result = response.json()
    content = result['choices'][0]['message']['content'].strip()
    return content


def safe_model_name(model: str) -> str:
    """Normalize model name for filesystem path.

    Examples:
        google/gemma-4-26B-A4B → google_gemma_4_26B_A4B
        Qwen/Qwen3.5-122B-A10B-FP8 → Qwen_Qwen3.5_122B_A10B_FP8
    """
    return model.replace("/", "_").replace("-", "_").replace(":", "_")


def main():
    parser = argparse.ArgumentParser(description="NLU evaluation client (gpustack endpoint).")
    parser.add_argument("--model", default="qwen/qwen3-32b", help="Model name (default: qwen/qwen3-32b)")
    parser.add_argument(
        "--prompt",
        default=None,
        help="Prompt YAML file path. Omit to run all ./prompt/*.yaml (or fallback to jjajangmyeon.yaml).",
    )
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help=f"Chat completions endpoint (default: {DEFAULT_ENDPOINT})")
    args = parser.parse_args()

    model = args.model
    prompt_arg = args.prompt
    endpoint = args.endpoint

    if prompt_arg:
        prompt_paths = [Path(prompt_arg)]
    else:
        prompt_paths = sorted(PROMPT_DIR.glob("*.yaml"))
        if not prompt_paths:
            prompt_paths = [PROMPT_DIR / "jjajangmyeon.yaml"]

    base_dir = get_base_dir()
    timestamp = get_timestamp()
    model_out_dir = base_dir / "results" / safe_model_name(model) / timestamp / "language" / "nlu"
    model_out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[nlu] BASE={base_dir}")
    print(f"[nlu] OUTPUT={model_out_dir}")

    for prompt_path in prompt_paths:
        # 상대 경로면 nlu_test 기준으로 해석
        if not prompt_path.is_absolute():
            candidate = (SCRIPT_DIR / prompt_path).resolve()
            prompt_path = candidate

        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt = f.read()

        print("프롬프트 파일:", str(prompt_path))
        print("프롬프트:")
        print(prompt)
        print("\n" + "=" * 50 + "\n")

        # API 호출
        response = get_response(prompt, model, endpoint)

        # 결과 저장
        output = {
            "model": model,
            "prompt_file": str(prompt_path),
            "prompt": prompt,
            "response": response,
        }

        out_name = f"{prompt_path.stem}.json"
        output_file = model_out_dir / out_name
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        print("응답:")
        print(response)
        print(f"\nResults saved to {output_file}")


if __name__ == "__main__":
    main()
