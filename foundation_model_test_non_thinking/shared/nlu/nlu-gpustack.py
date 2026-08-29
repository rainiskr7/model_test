import requests
import hashlib
import json
import os
import sys
import tempfile
import argparse
import importlib
from datetime import datetime
from pathlib import Path
try:
    _dotenv = importlib.import_module("dotenv")
    _dotenv.load_dotenv()
except Exception:
    # python-dotenv 는 선택 의존이고 실제로 없는 환경이 있다. 그때 조용히 넘어가면
    # 자격증명 없이 `Bearer None` 을 보내고 엔드포인트는 401 만 돌려준다 —
    # 인증 설정 문제가 서버 문제처럼 보인다. 최소 파서로 직접 읽는다.
    for _candidate in (Path.cwd(), *Path.cwd().parents, Path(__file__).resolve().parent.parent.parent):
        _env_file = _candidate / ".env"
        if not _env_file.is_file():
            continue
        try:
            for _line in _env_file.read_text(encoding="utf-8").splitlines():
                _line = _line.strip()
                if not _line or _line.startswith("#") or "=" not in _line:
                    continue
                _name, _, _value = _line.partition("=")
                os.environ.setdefault(_name.strip(), _value.strip().strip("\"'"))
        except Exception:
            pass
        break

api_key = os.getenv("OPENAI_API_KEY")

SCRIPT_DIR = Path(__file__).resolve().parent
PROMPT_DIR = SCRIPT_DIR / "prompt"
DEFAULT_ENDPOINT = "http://172.16.1.81:18090/v1/chat/completions"

# shared/ 를 import path 에 추가 (vsm/nlu 는 shared/nlu 로의 symlink 라 resolve 필요)
sys.path.insert(0, str(SCRIPT_DIR.parent))
from serving.constraints import apply as apply_serving_constraints  # noqa: E402
from serving.constraints import constraint_snapshot  # noqa: E402
sys.path.insert(0, str(SCRIPT_DIR / "scoring"))
from contract import digest as _digest, items_for, load_contract, render  # noqa: E402


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


def get_response(prompt, model, endpoint: str, timeout: float = 600.0,
                 request_snapshot: dict | None = None):
    """프롬프트를 입력받아 모델의 응답을 반환

    timeout: 네트워크 hang 방지용 (default 600초 = 10분)
    큰 모델 (27B dense) + max_tokens 8192 조합에서 120초로는 부족했음.
    """
    if request_snapshot is None:
        request_snapshot = {}
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
    # 서빙 백엔드 제약 적용 (SERVING_* env 미설정 시 no-op).
    # 제약은 파라미터를 지우거나 상한을 낮춘다 — 그래서 기록해야 하는 것은 위에서
    # 적은 요청값이 아니라 **적용 후 실제로 보낸 값**이다.
    apply_serving_constraints(payload)
    request_snapshot.clear()
    request_snapshot.update({k: v for k, v in payload.items() if k != "messages"})

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
    # 요청한 이름이 아니라 **엔드포인트가 서빙했다고 말한 것**을 들고 나온다.
    # `qwen/qwen3-32b` 같은 이름은 alias 라 문자열이 그대로여도 리비전이 바뀐다 —
    # 응답의 model/id/system_fingerprint 가 없으면 산출물만 보고는 두 런이 같은
    # 가중치에서 나왔는지 말할 수 없다.
    served = {
        "model": result.get("model"),
        "id": result.get("id"),
        "system_fingerprint": result.get("system_fingerprint"),
        "usage": result.get("usage"),
    }
    return content, {key: value for key, value in served.items() if value is not None}


def safe_model_name(model: str) -> str:
    """Normalize model name for filesystem path.

    Examples:
        google/gemma-4-26B-A4B → google_gemma_4_26B_A4B
        Qwen/Qwen3.5-122B-A10B-FP8 → Qwen_Qwen3.5_122B_A10B_FP8
    """
    return model.replace("/", "_").replace("-", "_").replace(":", "_")


MANIFEST_NAME = "run.json"
MANIFEST_SCHEMA_VERSION = 1


def results_model_dir_name(base_dir: Path, model: str) -> str:
    """이미 있는 모델 디렉토리의 **실제 표기**를 재사용한다.

    macOS 는 대소문자를 무시해 드러나지 않지만 리눅스에서는
    ``results/google_gemma_4_26B_A4B_it`` 와 ``results/google_gemma_4_26b_a4b_it`` 가
    서로 다른 디렉토리가 되어 한 런의 산출물이 둘로 갈린다. 이 저장소의 results/ 에는
    두 표기가 실제로 모두 들어 있다.
    """

    requested = safe_model_name(model)
    results_root = Path(base_dir) / "results"
    if not results_root.is_dir():
        return requested
    matches = sorted(
        entry.name
        for entry in results_root.iterdir()
        if entry.is_dir() and entry.name.casefold() == requested.casefold()
    )
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError(
            f"case-fold ambiguous results model directory for {requested!r}: {matches}"
        )
    return requested


def write_json_atomic(path: Path, payload) -> None:
    """임시 파일에 쓰고 rename 한다.

    직접 쓰기는 중간에 끊기면 잘린 JSON 을 남기는데, 그 파일은 "런이 실패했다" 가
    아니라 "산출물이 깨졌다" 로 보인다 — 나중에 읽는 쪽에서 구분할 수 없다.
    """

    # 고정된 ``<name>.tmp`` 를 쓰면 두 프로세스가 서로의 임시 파일을 덮어써
    # rename 전에 내용이 섞이거나 사라진다. 프로세스마다 고유한 이름을 쓴다.
    # (락은 아니다 — 마지막 rename 이 이긴다. 다만 부분적으로 섞인 파일은 없다.)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def repo_relative(base_dir: Path, path: Path) -> str:
    """저장소 상대 경로. 실패하면 절대 경로 그대로.

    절대 경로를 그대로 적으면 산출물에 실행 호스트의 홈 디렉토리가 박힌다 — 실제로
    커밋된 파일들에 ``/home/rainis/...`` 가 남아 있고, 그래서 내용이 같은 산출물이
    경로 차이만으로 서로 다른 파일로 갈렸다.
    """

    try:
        return str(path.resolve().relative_to(Path(base_dir).resolve()))
    except ValueError:
        return str(path)


def load_manifest(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        # 읽을 수 없는 매니페스트를 "없음"으로 취급하면 덮어쓰기 방어가 사라진다.
        raise SystemExit(f"[nlu] 기존 매니페스트를 읽을 수 없다: {path}")


def check_no_clobber(manifest, model: str, endpoint: str) -> None:
    """같은 디렉토리를 다른 런이 이미 쓰고 있으면 멈춘다.

    ``safe_model_name`` 은 ``/``, ``-``, ``:`` 를 모두 ``_`` 로 보낸다. 따라서
    ``a/b``, ``a-b``, ``a:b`` 는 한 디렉토리를 가리킨다. 매핑 자체는 바꿀 수 없다 —
    저장소의 results/ 트리 전체가 그 표기로 되어 있다. 대신 요청한 이름과
    엔드포인트를 매니페스트에 남겨서, 조용한 덮어쓰기를 **실패**로 바꾼다.
    """

    if manifest is None:
        return
    for field, current in (("requested_model", model), ("endpoint", endpoint)):
        previous = manifest.get(field)
        if previous is not None and previous != current:
            raise SystemExit(
                f"[nlu] 이 세션 디렉토리는 이미 다른 런의 것이다 — {field}: "
                f"{previous!r} vs {current!r}. 덮어쓰면 앞선 산출물이 사라진다. "
                "EVAL_TIMESTAMP 로 다른 세션을 지정하라."
            )


def main():
    parser = argparse.ArgumentParser(description="NLU evaluation client (gpustack endpoint).")
    parser.add_argument("--model", default="qwen/qwen3-32b", help="Model name (default: qwen/qwen3-32b)")
    parser.add_argument(
        "--prompt",
        default=None,
        help="Prompt YAML file path. Omit to run all ./prompt/*.yaml (or fallback to jjajangmyeon.yaml).",
    )
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help=f"Chat completions endpoint (default: {DEFAULT_ENDPOINT})")
    parser.add_argument(
        "--no-contract",
        action="store_true",
        help="응답 형식 계약을 덧붙이지 않는다 (계약 도입 이전 규약을 그대로 재현).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="같은 세션의 기존 산출물을 다시 만든다 (기본은 완료된 프롬프트를 건너뛴다).",
    )
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
    model_out_dir = (
        base_dir / "results" / results_model_dir_name(base_dir, model)
        / timestamp / "language" / "nlu"
    )
    model_out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[nlu] BASE={base_dir}")
    print(f"[nlu] OUTPUT={model_out_dir}")

    # 상대 경로면 nlu 스크립트 기준으로 해석 — 루프 전에 확정해야 기대 목록을 적을 수 있다.
    prompt_paths = [
        path if path.is_absolute() else (SCRIPT_DIR / path).resolve()
        for path in prompt_paths
    ]

    if not api_key:
        # 없는 채로 보내면 엔드포인트는 401 만 준다. 무엇이 없는지 여기서 말한다.
        raise SystemExit(
            "[nlu] OPENAI_API_KEY 가 없다 — 환경변수나 <BASE>/.env 에 설정하라."
        )

    contract = load_contract()
    manifest_path = model_out_dir / MANIFEST_NAME
    manifest = load_manifest(manifest_path)
    check_no_clobber(manifest, model, endpoint)

    expected = [path.stem for path in prompt_paths]
    # stem 만으로는 프롬프트가 식별되지 않는다. ``prompt/carwash.yaml`` 과
    # ``/tmp/carwash.yaml`` 은 stem 이 같아 기대 집합 검사를 통과하고, 이어서
    # 다른 본문의 응답을 같은 파일에 덮어쓴다. 본문 해시로 묶는다.
    prompt_identity = {
        path.stem: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in prompt_paths
    }
    # 매니페스트의 완료 표시를 그대로 믿지 않는다. 산출물이 지워졌거나 동기화가
    # 깨졌으면 파일 없이 complete 로 표시되고, 채점기는 그것을 "모델이 형식을
    # 지키지 않았다"로 집계한다 — 없는 파일이 모델의 오답으로 둔갑한다.
    done = [] if args.overwrite else [
        stem for stem in ((manifest or {}).get("completed_prompts") or [])
        if (model_out_dir / f"{stem}.json").is_file()
    ]
    if manifest is not None and sorted((manifest.get("expected_prompts") or [])) != sorted(expected):
        # 프롬프트 집합이 다르면 같은 시도가 아니다. 이어붙이면 한 디렉토리 안에서
        # 두 다른 측정이 섞여 완결된 한 런처럼 보인다.
        raise SystemExit(
            f"[nlu] 이 세션의 프롬프트 집합이 다르다: "
            f"{manifest.get('expected_prompts')} vs {expected}. "
            "EVAL_TIMESTAMP 로 다른 세션을 지정하라."
        )
    previous_identity = (manifest or {}).get("prompt_identity") or {}
    changed = sorted(
        stem for stem, digest in prompt_identity.items()
        if previous_identity.get(stem) not in (None, digest)
    )
    if changed:
        raise SystemExit(
            f"[nlu] 같은 이름의 프롬프트인데 본문이 다르다: {changed}. "
            "이어서 쓰면 두 다른 측정이 한 디렉토리에 섞인다 — "
            "EVAL_TIMESTAMP 로 다른 세션을 지정하라."
        )
    # 본문이 바뀐 프롬프트는 완료로 물려받지 않는다.
    done = [stem for stem in done if previous_identity.get(stem) in (None, prompt_identity[stem])]

    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        # 요청한 원본 이름. 디렉토리 이름은 손실 변환이라 여기서만 복구할 수 있다.
        "requested_model": model,
        "endpoint": endpoint,
        "serving_constraints": constraint_snapshot(),
        # 형제 트랙은 `python` 을 부르는데 그 이름이 없는 환경이 실재한다.
        # 어떤 인터프리터가 이 산출물을 만들었는지는 재현할 때 필요하다.
        "python_executable": sys.executable,
        # 계약이 있는 런과 없는 런은 다른 규약이다. 채점기는 계약이 기록되지
        # 않은 런을 채점 대상에서 뺀다 — 섞이면 둘 다 못 믿는다.
        "answer_contract": None if args.no_contract else {
            "version": contract["version"],
            "sha256": {stem: _digest(render(contract, stem)) for stem in expected},
        },
        "expected_prompts": expected,
        # 이름이 아니라 본문으로 식별한다.
        "prompt_identity": prompt_identity,
        "completed_prompts": done,
        # 완결 여부를 파일 개수로 추정하지 않는다 — 한 개짜리 정상 런과
        # 두 개 중 하나만 성공한 런이 구분되지 않기 때문이다.
        "status": "running",
        "started_at": datetime.now().astimezone().isoformat(),
        "completed_at": None,
        "failure": None,
    }
    write_json_atomic(manifest_path, manifest)

    def finalize(failure=None) -> None:
        manifest["status"] = (
            "complete"
            if not failure and sorted(manifest["completed_prompts"]) == sorted(expected)
            else "partial"
        )
        manifest["completed_at"] = datetime.now().astimezone().isoformat()
        manifest["failure"] = failure
        write_json_atomic(manifest_path, manifest)

    try:
        for prompt_path in prompt_paths:
            if prompt_path.stem in done:
                print(f"[nlu] 이미 완료됨, 건너뜀: {prompt_path.stem} (--overwrite 로 재실행)")
                continue

            with open(prompt_path, "r", encoding="utf-8") as f:
                prompt = f.read()

            # 본문은 바이트 그대로 두고 계약만 뒤에 덧붙인다. 본문을 고치면 이미
            # 커밋된 산출물과 비교할 수 없게 된다.
            addendum = "" if args.no_contract else render(contract, prompt_path.stem)
            sent = prompt + addendum

            print("프롬프트 파일:", str(prompt_path))
            print("프롬프트:")
            print(prompt)
            print("\n" + "=" * 50 + "\n")

            # API 호출
            request_snapshot: dict = {}
            response, served = get_response(
                sent, model, endpoint, request_snapshot=request_snapshot
            )

            # 결과 저장
            output = {
                "model": model,
                # 기존 산출물과의 호환을 위해 남기되, 호스트 홈 디렉토리가 박히지
                # 않도록 저장소 상대 경로로 적는다.
                "prompt_file": repo_relative(base_dir, prompt_path),
                "prompt": prompt,
                "response": response,
                "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                # 실제로 보낸 본문 = prompt + 계약. 둘을 따로 적어야 계약을 바꿨을 때
                # 무엇이 달라졌는지가 보인다.
                "prompt_sent_sha256": hashlib.sha256(sent.encode("utf-8")).hexdigest(),
                "answer_contract": None if not addendum else {
                    "version": contract["version"],
                    "sha256": _digest(addendum),
                    "items": [item["id"] for item in items_for(contract, prompt_path.stem)],
                },
                "endpoint": endpoint,
                "served_identity": served,
                "request": request_snapshot,
                "serving_constraints": constraint_snapshot(),
            }

            output_file = model_out_dir / f"{prompt_path.stem}.json"
            write_json_atomic(output_file, output)
            manifest["completed_prompts"].append(prompt_path.stem)
            write_json_atomic(manifest_path, manifest)

            print("응답:")
            print(response)
            print(f"\nResults saved to {output_file}")
    except BaseException as exc:
        # 실패해도 종료코드는 그대로 전파한다. 매니페스트는 남은 파일이 부분
        # 산출물이라는 사실만 기록한다.
        finalize(f"{type(exc).__name__}: {exc}")
        raise
    finalize()


if __name__ == "__main__":
    main()
