#!/usr/bin/env python3
"""Pinned tau2-bench를 no-user telecom 공식 split으로 실행한다."""

import argparse
import importlib.metadata
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional


SOURCE_COMMIT = "c3398666e6559e3a063da3fc04b5acf7f941464e"
DEFAULT_SPLIT = "test"
JUDGE_BASES = frozenset({"NL_ASSERTION", "COMMUNICATE"})
PROGRAMMATIC_BASES = frozenset({"DB", "ENV_ASSERTION", "ACTION"})


def safe_model_name(model: str) -> str:
    return model.replace("/", "_").replace("-", "_").replace(":", "_")


def normalize_api_base(base_url: str) -> str:
    """LiteLLM OpenAI provider가 기대하는 API root로 정규화한다."""
    value = base_url.rstrip("/")
    suffix = "/chat/completions"
    return value[: -len(suffix)] if value.endswith(suffix) else value



def litellm_model_name(model: str) -> str:
    """litellm provider 접두사를 붙인다. 이미 있으면 덧붙이지 않는다.

    로컬 서빙 모델은 'qwen_qwen3.5_35b_a3b_fp8' 처럼 접두사가 없어 'openai/' 가 필요하다.
    반면 OpenRouter 모델명은 'openai/gpt-4.1-mini' 처럼 이미 provider 를 포함한다.
    무조건 붙이면 'openai/openai/gpt-4.1-mini' 가 된다 (2026-08-23 실제로 발생).
    """
    return model if "/" in model else f"openai/{model}"


def build_litellm_args(
    api_base: str, request_timeout: float, max_tokens: int
) -> dict[str, Any]:
    """Diffusion endpoint에 sampling parameter를 강제로 보내지 않는다."""
    return {
        "api_base": api_base,
        "timeout": request_timeout,
        "num_retries": 0,
        "max_tokens": max_tokens,
    }


def reward_basis(task: Mapping[str, Any]) -> tuple[str, ...]:
    criteria = task.get("evaluation_criteria") or {}
    return tuple(sorted(str(value) for value in criteria.get("reward_basis") or []))


def requires_judge(task: Mapping[str, Any]) -> bool:
    """이 태스크를 채점하려면 LLM 판정이 필요한가.

    reward_basis 선언만 보면 안 된다. 두 가지 이유다.

    1. COMMUNICATE 는 판정이 아니다. evaluator_communicate.py 가
       `info_str.lower() in message.content.lower()` 로 부분문자열을 찾는다.
       (취약한 매칭이지 의미 판정이 아니다 — 결과 해석 시 유의할 것.)

    2. NL_ASSERTION 은 **선언돼 있어도 내용이 비면 판정을 부르지 않는다.**
       evaluator_nl_assertions.py:37 이 nl_assertions 가 비면 판정 없이 1.0 을
       돌려준다. retail test 40건 중 39건이 NL_ASSERTION 을 선언하지만 실제 내용이
       있는 것은 11건뿐이라, 선언만 보면 29건을 잘못 배제한다.

    telecom 은 ENV_ASSERTION / ACTION 만 쓰므로 이 함수의 도입으로 거동이 바뀌지 않는다.
    """
    criteria = task.get("evaluation_criteria") or {}
    basis = {str(b) for b in (criteria.get("reward_basis") or [])}
    if "NL_ASSERTION" in basis and criteria.get("nl_assertions"):
        return True
    return False


def is_programmatic_basis(basis: Iterable[str]) -> bool:
    values = frozenset(str(value) for value in basis)
    return bool(values) and not (values & JUDGE_BASES) and values <= PROGRAMMATIC_BASES


def _load_tasks(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError(f"expected a task list: {path}")
    return data


def _load_task_splits(path: Path) -> dict[str, list[str]]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict) or not all(
        isinstance(name, str) and isinstance(ids, list) for name, ids in data.items()
    ):
        raise ValueError(f"expected a split mapping: {path}")
    return {name: [str(task_id) for task_id in ids] for name, ids in data.items()}


def resolve_task_split(
    tasks: Iterable[Mapping[str, Any]],
    split_path: Path,
    split_name: str,
    domain: str = "telecom",
) -> dict[str, Any]:
    """공식 split 순서를 보존하고 judge-free 실행 목록을 만든다."""
    splits = _load_task_splits(split_path)
    available = sorted(splits)
    if split_name not in splits:
        raise ValueError(
            f"unknown telecom split {split_name!r}; available splits: "
            f"{', '.join(available)}"
        )

    split_ids = splits[split_name]
    if len(split_ids) != len(set(split_ids)):
        raise ValueError(f"telecom split {split_name!r} contains duplicate task ids")
    tasks_by_id = {str(task["id"]): task for task in tasks}
    missing = [task_id for task_id in split_ids if task_id not in tasks_by_id]
    if missing:
        raise ValueError(
            f"telecom split {split_name!r} references missing canonical tasks: {missing}"
        )

    runnable_ids: list[str] = []
    not_measured_tasks: list[dict[str, Any]] = []
    for task_id in split_ids:
        task = tasks_by_id[task_id]
        basis = reward_basis(task)
        if not requires_judge(task):
            runnable_ids.append(task_id)
            continue
        reason = "llm_judge_required"
        not_measured_tasks.append(
            {"task_id": task_id, "reward_basis": list(basis), "reason": reason}
        )

    return {
        "domain": domain,
        "name": split_name,
        "source": f"data/tau2/domains/{domain}/split_tasks.json",
        "task_count": len(split_ids),
        "runnable_task_count": len(runnable_ids),
        "task_ids": runnable_ids,
        "not_measured_task_count": len(not_measured_tasks),
        "not_measured_tasks": not_measured_tasks,
    }


def build_upstream_command(
    args: argparse.Namespace,
    llm_args: Mapping[str, Any],
    user_llm_args: Mapping[str, Any],
    upstream_dir: Path,
    task_ids: Iterable[str],
) -> list[str]:
    """tau2 CLI에 공식 split과 실제 실행 id를 함께 전달한다."""
    selected_ids = list(task_ids)
    return [
        sys.executable,
        "-m",
        "tau2.cli",
        "run",
        "--domain",
        args.domain,
        "--agent",
        "llm_agent_solo" if args.mode == "solo" else "llm_agent",
        "--agent-llm",
        litellm_model_name(args.model),
        "--agent-llm-args",
        json.dumps(llm_args, separators=(",", ":")),
        "--user",
        "dummy_user" if args.mode == "solo" else "user_simulator",
        *(
            []
            if args.mode == "solo"
            else [
                "--user-llm",
                litellm_model_name(args.user_model or args.model),
                "--user-llm-args",
                json.dumps(user_llm_args, separators=(",", ":")),
            ]
        ),
        "--task-split-name",
        args.split,
        "--task-ids",
        *selected_ids,
        "--num-trials",
        "1",
        "--max-steps",
        str(args.max_steps),
        "--timeout",
        str(args.task_timeout),
        "--max-concurrency",
        str(args.max_concurrency),
        "--max-retries",
        "0",
        "--hallucination-retries",
        "0",
        "--retry-delay",
        "0",
        "--save-to",
        str(upstream_dir),
        "--verbose-logs",
        "--llm-log-mode",
        "all",
    ]



def redact_secrets_in_upstream(upstream_dir: Path) -> int:
    """tau2 가 쓴 산출물에서 자격증명을 지운다. 지운 파일 수를 돌려준다.

    tau2 는 info.agent_info.llm_args / user_info.llm_args 를 **그대로** results.json 에
    적고, --llm-log-mode all 이면 호출별 덤프에도 남긴다. 우리가 외부 API 키를
    llm_args 로 넘기므로 그대로 두면 키가 산출물에 박힌다.

    2026-08-23 에 실제로 발생했다 — GitHub 푸시 보호가 막아 유출 직전에 걸렸다.
    결과 파일은 버전관리 대상이므로 러너가 기록 직후 반드시 지워야 한다.
    """
    redacted = 0
    for path in upstream_dir.rglob("*.json"):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if '"api_key"' not in text:
            continue
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            continue
        if _scrub_api_key(data):
            _write_atomic(path, data)
            redacted += 1
    return redacted


def _scrub_api_key(node: Any) -> bool:
    """중첩 구조를 훑어 api_key 값을 치환한다. 바꾼 게 있으면 True."""
    changed = False
    if isinstance(node, dict):
        for key, value in list(node.items()):
            if key == "api_key" and isinstance(value, str) and value:
                node[key] = "***REDACTED***"
                changed = True
            elif _scrub_api_key(value):
                changed = True
    elif isinstance(node, list):
        for item in node:
            if _scrub_api_key(item):
                changed = True
    return changed


def _write_atomic(path: Path, data: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def _package_version(name: str) -> Optional[str]:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _timestamp(base_dir: Path) -> str:
    value = os.environ.get("EVAL_TIMESTAMP")
    if value:
        return value
    session_file = base_dir / ".eval_session"
    if session_file.is_file():
        value = session_file.read_text(encoding="utf-8").strip()
    return value or datetime.now().strftime("%Y%m%d_%H%M%S")


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    # solo: 상류가 "Advanced: Ablation Studies" 로 문서화한 사용자 없는 변형.
    # standard: 실제 tau2 프로토콜(에이전트-사용자-툴 3자). test 분할 보상은 어느 쪽이든
    #   DB/ENV_ASSERTION/ACTION 기반이라 판정 모델이 필요 없다 — 사용자 시뮬레이터는
    #   판정자가 아니다.
    parser.add_argument("--mode", choices=("solo", "standard"), default="solo")
    # standard 모드의 사용자 시뮬레이터 모델. **필수다.**
    #
    # 예전엔 생략하면 에이전트와 같은 모델을 썼다. 그 결과 모델 비교가 오염됐다 —
    # qwen 런은 qwen 이 사용자를, gemma 런은 gemma 가 사용자를 연기해서 두 런의
    # 환경이 서로 달랐다. 사용자 시뮬레이터가 약하면 과제가 쉬워질 수도 어려워질
    # 수도 있어 방향조차 알 수 없다. 2026-08-23 에 발견.
    #
    # 상류 기본값은 고정 3자 모델이다 (config.py:17 DEFAULT_LLM_USER =
    # "gpt-4.1-2025-04-14"). 후보 모델을 사용자로 쓰는 것은 상류 설계가 아니다.
    # 조용한 기본값 대신 운영자가 명시적으로 고르게 한다.
    # 실행 도메인. telecom 은 판정 불필요 40/40, retail 은 29/40 (나머지는
    # nl_assertions 내용이 있어 판정이 필요하다). airline 은 20/20 전부 판정 필요라
    # 이 트랙에서 돌 수 없다.
    parser.add_argument("--domain", default="telecom")
    parser.add_argument("--user-model", default=None)
    # 사용자 시뮬레이터를 에이전트와 **다른 엔드포인트**로 보낼 때 쓴다.
    # 상류 기본값이 외부 모델(gpt-4.1)이므로 이게 정상 형태다. 생략하면 에이전트와
    # 같은 엔드포인트를 쓴다(로컬 제3 모델을 사용자로 세우는 경우).
    parser.add_argument("--user-base-url", default=None)
    # 사용자 엔드포인트의 API 키. 값을 CLI 로 받지 않는다 — 프로세스 목록에 노출된다.
    # 환경변수 이름만 받고 값은 러너가 읽는다. 기본 TAUBENCH_USER_API_KEY.
    parser.add_argument("--user-api-key-env", default="TAUBENCH_USER_API_KEY")
    parser.add_argument(
        "--base-url", default="http://172.16.1.81:18090/v1/chat/completions"
    )
    parser.add_argument("--track-name", default="taubench")
    parser.add_argument(
        "--split", default=os.environ.get("TAUBENCH_SPLIT", DEFAULT_SPLIT)
    )
    parser.add_argument("--request-timeout", type=float, default=60.0)
    parser.add_argument("--task-timeout", type=float, default=600.0)
    parser.add_argument("--max-retries", type=int, default=0)
    parser.add_argument("--max-tokens", type=int, default=16384)
    parser.add_argument("--max-concurrency", type=int, default=1)
    parser.add_argument("--max-steps", type=int, default=100)
    return parser.parse_args(argv)


def _validate_args(args: argparse.Namespace) -> None:
    if args.request_timeout <= 0 or args.task_timeout <= 0:
        raise ValueError("request/task timeouts must be positive")
    if args.task_timeout <= args.request_timeout:
        raise ValueError("task timeout must be greater than request timeout")
    if args.max_retries != 0:
        raise ValueError("taubench requires max_retries=0 for visible, comparable runs")
    if not args.split:
        raise ValueError("split name must not be empty")
    if args.mode == "standard" and not args.user_model:
        raise SystemExit(
            "standard 모드에는 --user-model 이 필요합니다 (TAUBENCH_USER_MODEL).\n"
            "  생략하면 후보 모델이 사용자 시뮬레이터를 겸해 모델 간 비교가 오염됩니다.\n"
            "  모든 후보에 대해 **같은** 사용자 모델을 지정하세요."
        )
    if args.max_tokens < 1 or args.max_concurrency < 1 or args.max_steps < 1:
        raise ValueError("max tokens/concurrency/steps must be positive")


def main(argv: Optional[list[str]] = None) -> int:
    try:
        args = parse_args(argv)
        _validate_args(args)
        base_dir = Path(
            os.environ.get("MODEL_TEST_BASE") or Path(__file__).resolve().parents[3]
        ).resolve()
        bench_dir = base_dir / "data" / "tau2-bench"
        actual_commit = subprocess.check_output(
            ["git", "-C", str(bench_dir), "rev-parse", "HEAD"], text=True
        ).strip()
        if actual_commit != SOURCE_COMMIT:
            raise ValueError(
                f"tau2-bench commit mismatch: expected {SOURCE_COMMIT}, got {actual_commit}"
            )

        domain_dir = bench_dir / "data" / "tau2" / "domains" / args.domain
        canonical_path = domain_dir / "tasks.json"
        split_path = domain_dir / "split_tasks.json"
        tasks = _load_tasks(canonical_path)
        split = resolve_task_split(tasks, split_path, args.split, args.domain)
        selected_ids = list(split["task_ids"])
        if not selected_ids:
            raise ValueError(
                f"{args.domain} split {args.split!r} has no judge-free runnable tasks"
            )
        timestamp = _timestamp(base_dir)
        results_dir = (
            base_dir
            / "results"
            / safe_model_name(args.model)
            / timestamp
            / "language"
            / args.track_name
        )
        upstream_dir = results_dir / "upstream" / args.domain
        api_base = normalize_api_base(args.base_url)
        llm_args = build_litellm_args(api_base, args.request_timeout, args.max_tokens)

        # 사용자 시뮬레이터 llm_args. 별도 엔드포인트를 주면 그쪽으로, 아니면
        # 에이전트와 같은 곳으로 보낸다. 키는 환경변수에서만 읽는다.
        user_llm_args = dict(llm_args)
        if args.mode == "standard":
            user_model = args.user_model or args.model
            is_external = "/" in user_model and not user_model.startswith("openai/")
            if args.user_base_url:
                user_llm_args["api_base"] = normalize_api_base(args.user_base_url)
            elif is_external:
                # **에이전트의 api_base 를 물려받으면 안 된다.** user_llm_args 는
                # llm_args 를 복사해 만들므로 로컬 서빙 주소가 들어 있다. provider
                # 접두사가 있는 외부 모델은 litellm 이 자기 엔드포인트를 아는데,
                # api_base 가 남아 있으면 그쪽으로 보내 401 이 난다
                # (2026-08-23 airline 첫 런에서 20/20 AuthenticationError).
                user_llm_args.pop("api_base", None)
            if is_external or args.user_base_url:
                # **키를 llm_args 에 넣지 않는다.** tau2 는 llm_args 를 results.json 에
                # 그대로 적으므로 넣으면 산출물에 자격증명이 박힌다 (2026-08-23 에
                # 실제로 발생, GitHub 푸시 보호가 두 번 막았다).
                #
                # litellm 은 provider 접두사에 따라 환경변수에서 키를 읽는다:
                #   openrouter/...  -> OPENROUTER_API_KEY  (main.py:3283)
                # 따라서 모델명을 openrouter/openai/gpt-4.1-mini 형태로 주면
                # api_base 도 api_key 도 인자로 넘길 필요가 없다.
                user_api_key = os.environ.get(args.user_api_key_env)
                if not user_api_key:
                    raise SystemExit(
                        f"외부 사용자 시뮬레이터에는 {args.user_api_key_env} 환경변수가 "
                        "필요합니다 (값은 인자로 넘기지 않습니다)."
                    )
                # litellm 이 읽을 자리에 옮겨 담는다. 자식 프로세스 env 로만 전달된다.
                os.environ.setdefault("OPENROUTER_API_KEY", user_api_key)
                # 상류는 사용자 시뮬레이터에 temperature=0 을 명시한다
                # (config.py DEFAULT_LLM_ARGS_USER). 외부 API 는 이를 받는다.
                user_llm_args["temperature"] = 0.0
        manifest: dict[str, Any] = {
            "status": "running",
            "model": args.model,
            "track": args.track_name,
            "source": {
                "repository": "sierra-research/tau2-bench",
                "commit": SOURCE_COMMIT,
                "license": "MIT",
            },
            "split": split,
            # 실행 도메인만 runnable 로 적고 나머지는 미실행 사유를 남긴다.
            # 판정 불필요 태스크 수는 requires_judge() 로 판정한다 (선언이 아니라
            # nl_assertions 내용 유무 기준). 2026-08-23 실측:
            #   telecom test 40/40, retail test 29/40, airline test 0/20
            "domain_scope": {
                d: (
                    {"runnable": True, "user_mode": args.mode}
                    if d == args.domain
                    else {"runnable": False, "reason": "not selected for this run"}
                )
                for d in ("telecom", "retail", "airline", "banking_knowledge")
            },
            "harness_integrity": {
                "architecture": "upstream_tau2_framework",
                # 채점기의 무결성 대조는 이 값에서 기대 구현명을 파생시킨다.
                # 매니페스트는 "우리가 무엇을 돌렸다고 주장하는가", upstream results.info 는
                # "실제로 무엇이 돌았는가" 다 — 둘을 대조하는 것이 검사의 요지다.
                "mode": args.mode,
                "agent_implementation": (
                    "llm_agent_solo" if args.mode == "solo" else "llm_agent"
                ),
                "user_implementation": (
                    "dummy_user" if args.mode == "solo" else "user_simulator"
                ),
                "user_model_sent_to_litellm": (
                    None
                    if args.mode == "solo"
                    else litellm_model_name(args.user_model or args.model)
                ),
                "provider": "litellm_openai_compatible",
                "model_requested": args.model,
                "model_sent_to_litellm": litellm_model_name(args.model),
                "api_base": api_base,
                "api_key_source": "OPENAI_API_KEY environment variable",
                "request_timeout": args.request_timeout,
                "task_timeout": args.task_timeout,
                "framework_max_retries": 0,
                "litellm_num_retries": 0,
                "max_tokens": args.max_tokens,
                "temperature_sent": False,
                "serving_profile_applied": False,
                "serving_profile_observable": False,
                "max_concurrency": args.max_concurrency,
                "max_steps": args.max_steps,
                "tau2_version": _package_version("tau2"),
                "litellm_version": _package_version("litellm"),
                "openai_sdk_version": _package_version("openai"),
                "successful_request_logs": True,
                "failed_request_attempts_observable": False,
                "absorbed_timeout_counter_observable": False,
            },
        }
        _write_atomic(results_dir / "run_manifest.json", manifest)

        env = os.environ.copy()
        env["TAU2_DATA_DIR"] = str(bench_dir / "data")
        command = build_upstream_command(
            args, llm_args, user_llm_args, upstream_dir, selected_ids
        )
        print(
            f"[taubench] telecom split {args.split!r}: "
            f"{len(selected_ids)}/{split['task_count']} judge-free tasks; "
            f"{split['not_measured_task_count']} not measured"
        )
        try:
            subprocess.run(command, cwd=bench_dir, env=env, check=True)
        finally:
            # 성공/실패와 무관하게 반드시 지운다. 실패한 런의 산출물도 커밋된다.
            n_redacted = redact_secrets_in_upstream(upstream_dir)
            if n_redacted:
                print(f"[taubench] api_key 를 {n_redacted}개 파일에서 제거했다")
        manifest["status"] = "completed"
        manifest["completed_at"] = datetime.now().isoformat()
        manifest["upstream_results"] = str(
            (upstream_dir / "results.json").relative_to(results_dir)
        )
        _write_atomic(results_dir / "run_manifest.json", manifest)
        print(f"[taubench] upstream artifacts written to {upstream_dir}")
        return 0
    except Exception as exc:
        print(f"[taubench] ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
