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
    tasks: Iterable[Mapping[str, Any]], split_path: Path, split_name: str
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
        basis = reward_basis(tasks_by_id[task_id])
        if is_programmatic_basis(basis):
            runnable_ids.append(task_id)
            continue
        reason = (
            "llm_judge_required"
            if set(basis) & JUDGE_BASES
            else "unsupported_reward_basis"
        )
        not_measured_tasks.append(
            {"task_id": task_id, "reward_basis": list(basis), "reason": reason}
        )

    return {
        "domain": "telecom",
        "name": split_name,
        "source": "data/tau2/domains/telecom/split_tasks.json",
        "task_count": len(split_ids),
        "runnable_task_count": len(runnable_ids),
        "task_ids": runnable_ids,
        "not_measured_task_count": len(not_measured_tasks),
        "not_measured_tasks": not_measured_tasks,
    }


def build_upstream_command(
    args: argparse.Namespace,
    llm_args: Mapping[str, Any],
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
        "telecom",
        "--agent",
        "llm_agent_solo" if args.mode == "solo" else "llm_agent",
        "--agent-llm",
        f"openai/{args.model}",
        "--agent-llm-args",
        json.dumps(llm_args, separators=(",", ":")),
        "--user",
        "dummy_user" if args.mode == "solo" else "user_simulator",
        *(
            []
            if args.mode == "solo"
            else [
                "--user-llm",
                f"openai/{args.user_model or args.model}",
                "--user-llm-args",
                json.dumps(llm_args, separators=(",", ":")),
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
    parser.add_argument("--user-model", default=None)
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

        telecom_dir = bench_dir / "data" / "tau2" / "domains" / "telecom"
        canonical_path = telecom_dir / "tasks.json"
        split_path = telecom_dir / "split_tasks.json"
        tasks = _load_tasks(canonical_path)
        split = resolve_task_split(tasks, split_path, args.split)
        selected_ids = list(split["task_ids"])
        if not selected_ids:
            raise ValueError(
                f"telecom split {args.split!r} has no judge-free runnable tasks"
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
        upstream_dir = results_dir / "upstream" / "telecom"
        api_base = normalize_api_base(args.base_url)
        llm_args = build_litellm_args(api_base, args.request_timeout, args.max_tokens)
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
            "domain_scope": {
                "telecom": {"runnable": True, "user_mode": "dummy_user"},
                "banking_knowledge": {
                    "runnable": False,
                    "reason": "banking_knowledge environment rejects solo mode",
                },
                "retail": {"runnable": False, "reason": "LLM-judge reward basis"},
                "airline": {"runnable": False, "reason": "LLM-judge reward basis"},
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
                    else f"openai/{args.user_model or args.model}"
                ),
                "provider": "litellm_openai_compatible",
                "model_requested": args.model,
                "model_sent_to_litellm": f"openai/{args.model}",
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
        command = build_upstream_command(args, llm_args, upstream_dir, selected_ids)
        print(
            f"[taubench] telecom split {args.split!r}: "
            f"{len(selected_ids)}/{split['task_count']} judge-free tasks; "
            f"{split['not_measured_task_count']} not measured"
        )
        subprocess.run(command, cwd=bench_dir, env=env, check=True)
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
