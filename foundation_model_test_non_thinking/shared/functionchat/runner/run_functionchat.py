#!/usr/bin/env python3
"""FunctionChat-Bench의 exact-match 가능 항목을 OpenAI-compatible 모델로 실행한다."""

import argparse
import importlib.util
import json
import os
import queue
import sys
import tempfile
import threading
import time
import types
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple


SOURCE_COMMIT = "5ddb0b5bb37d6423e1f3381ef693cda811a7847e"
CALL = "call"


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes")


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def expand_singlecall(path: Path, system_prompt: str) -> List[Dict[str, Any]]:
    """원본 SingleCallPayloadCreator와 같은 query × tool-set 순서로 펼친다."""
    items: List[Dict[str, Any]] = []
    for source_line, record in enumerate(_load_jsonl(path), start=1):
        for query_index, query in enumerate(record["query"]):
            ground_truth = json.loads(record["ground_truth"][query_index]["content"])
            acceptable = record["acceptable_arguments"][query_index]["content"]
            for tool_variant in record["tools"]:
                tools_type = tool_variant["type"]
                items.append(
                    {
                        "item_id": (
                            f"singlecall:{source_line}:{query['serial_num']}:{tools_type}"
                        ),
                        "dataset": "singlecall",
                        "source_line": source_line,
                        "query_index": query_index,
                        "serial_num": query["serial_num"],
                        "tools_type": tools_type,
                        "type_of_output": CALL,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": query["content"]},
                        ],
                        "tools": tool_variant["content"],
                        "ground_truth": ground_truth,
                        "acceptable_arguments": acceptable,
                    }
                )
    return items


def expand_call_decision(path: Path) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for source_line, record in enumerate(_load_jsonl(path), start=1):
        items.append(
            {
                "item_id": f"call_decision:{record['serial_num']}",
                "dataset": "call_decision",
                "source_line": source_line,
                "serial_num": record["serial_num"],
                "category": record.get("category"),
                "type_of_output": record["type_of_output"],
                "messages": record["input_messages"],
                "tools": record["input_tools"],
                "ground_truth": record["ground_truth"],
                "acceptable_arguments": record.get("acceptable_arguments"),
            }
        )
    return items



def expand_dialog(path: Path, system_prompt: str) -> List[Dict[str, Any]]:
    """Dialog 45개 시나리오를 평가 턴 단위로 펼친다 (총 200턴).

    상류도 시나리오가 아니라 턴 단위로 평가한다 (src/payload_creator.py 가 turns 를
    순회한다). 각 턴은 query 에 그 시점까지의 대화 이력을 통째로 들고 있어서
    singlecall/call_decision 과 같은 모양이다 — messages + tools + ground_truth.

    턴 유형 분포 (핀 데이터 실측): call 70 / completion 71 / slot 36 / relevance 23.
    call 70턴만 exact-match 로 결정론적 채점이 가능하고 나머지 130턴은 판정 모델이
    필요하다. 여기서는 전부 항목으로 만들되 call 이 아닌 것은 상위 루프가
    not_measured 로 처리한다 (singlecall/call_decision 과 같은 규칙).
    """
    items: List[Dict[str, Any]] = []
    for source_line, record in enumerate(_load_jsonl(path), start=1):
        tools = record["tools"]
        for turn in record["turns"]:
            messages = list(turn["query"])
            # 상류는 system prompt 를 대화 앞에 붙인다. query 가 이미 system 으로
            # 시작하면 중복해서 넣지 않는다.
            if not messages or messages[0].get("role") != "system":
                messages = [{"role": "system", "content": system_prompt}] + messages
            items.append(
                {
                    "item_id": f"dialog:{turn['serial_num']}",
                    "dataset": "dialog",
                    "source_line": source_line,
                    "serial_num": turn["serial_num"],
                    "category": None,
                    "dialog_num": record.get("dialog_num"),
                    "turn_num": turn.get("turn_num"),
                    "type_of_output": turn["type_of_output"],
                    "messages": messages,
                    "tools": tools,
                    "ground_truth": turn["ground_truth"],
                    "acceptable_arguments": turn.get("acceptable_arguments"),
                }
            )
    return items


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_shared_adapter(base_dir: Path):
    """shared adapter를 Ko-AgentBench의 최소 interface package 위에서 직접 로드한다."""
    koa_dir = base_dir / "data" / "Ko-AgentBench"
    shared_custom = base_dir / "shared" / "agent" / "gpustack_custom"
    required = (
        koa_dir / "bench" / "adapters" / "base_adapter.py",
        koa_dir / "bench" / "observability.py",
        shared_custom / "tool_call_parser.py",
        shared_custom / "openai_compat_adapter.py",
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"adapter dependencies missing: {missing}")

    # bench/adapters/__init__.py는 optional provider를 import하므로 실행하지 않는다.
    bench_package = types.ModuleType("bench")
    bench_package.__path__ = [str(koa_dir / "bench")]
    adapters_package = types.ModuleType("bench.adapters")
    adapters_package.__path__ = [str(koa_dir / "bench" / "adapters")]
    sys.modules["bench"] = bench_package
    sys.modules["bench.adapters"] = adapters_package
    _load_module(
        "bench.adapters.base_adapter", koa_dir / "bench" / "adapters" / "base_adapter.py"
    )
    _load_module("bench.observability", koa_dir / "bench" / "observability.py")
    _load_module("bench.adapters.tool_call_parser", shared_custom / "tool_call_parser.py")
    adapter_module = _load_module(
        "bench.adapters.functionchat_openai_compat_adapter",
        shared_custom / "openai_compat_adapter.py",
    )
    return adapter_module.OpenAICompatAdapter


def _call_with_budget(adapter: Any, item: Mapping[str, Any], timeout: float):
    result_queue: queue.Queue = queue.Queue(maxsize=1)

    def invoke() -> None:
        try:
            result_queue.put(
                (True, adapter.chat_completion(item["messages"], tools=item["tools"]))
            )
        except BaseException as exc:  # 호출 thread의 예외를 main thread로 전달한다.
            result_queue.put((False, exc))

    worker = threading.Thread(target=invoke, daemon=True)
    worker.start()
    worker.join(timeout)
    if worker.is_alive():
        raise TimeoutError(f"task timeout after {timeout:.3f}s remaining budget")
    ok, value = result_queue.get_nowait()
    if not ok:
        raise value
    return value


def run_item(
    adapter: Any,
    item: Mapping[str, Any],
    task_timeout: float,
    max_retries: int,
    evaluation_status: str = "measured",
) -> Dict[str, Any]:
    """모델을 호출하고 응답을 보존한다.

    evaluation_status 는 **exact-match 채점 대상인지**만 나타낸다. 호출은 어느 쪽이든
    한다 — not_measured 도 응답을 저장해야 나중에 판정 계층이 쓸 수 있다.
    (2026-08-23 이전에는 not_measured 항목의 생성을 아예 건너뛰어 model_output 과
     raw_response 가 130건 전부 null 이었고, 판정 계층을 붙일 수 없었다.)
    """
    started = time.monotonic()
    deadline = started + task_timeout
    errors: List[str] = []
    response = None
    completion_latency = 0.0
    attempts = 0

    for _ in range(max_retries):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            errors.append(f"TimeoutError: task timeout after {task_timeout}s")
            break
        attempts += 1
        attempt_started = time.monotonic()
        try:
            response = _call_with_budget(adapter, item, remaining)
            completion_latency = time.monotonic() - attempt_started
            break
        except Exception as exc:
            errors.append(f"{type(exc).__name__}: {exc}")
            if isinstance(exc, TimeoutError):
                break

    execution_time = time.monotonic() - started
    message = response.get("message", {}) if isinstance(response, dict) else {}
    tool_calls = message.get("tool_calls", []) if isinstance(message, dict) else []
    # content 도 함께 담는다. exact-match 는 tool_calls 만 보지만, 판정 계층은
    # 되묻기(slot) / 거절(relevance) / 완결(completion) 을 평가하므로 **자연어 응답이
    # 있어야 한다.** 예전엔 tool_calls 만 남겨서 판정 대상 응답이 통째로 없었다.
    model_output = {
        "tool_calls": tool_calls,
        "content": message.get("content") if isinstance(message, dict) else None,
    }
    return {
        **dict(item),
        "evaluation_status": evaluation_status,
        "model_output": model_output,
        "raw_response": response,
        "exact_match": None,
        "attempts": attempts,
        "error": errors[-1] if response is None and errors else None,
        "attempt_errors": errors,
        "execution_time": execution_time,
        "latency_seconds": execution_time,
        "completion_latency": {
            "average": completion_latency,
            "min": completion_latency,
            "max": completion_latency,
            "count": 1 if response is not None else 0,
            "unit": "seconds",
        },
        "finish_reason": response.get("finish_reason") if isinstance(response, dict) else None,
        "last_finish_reason": response.get("finish_reason") if isinstance(response, dict) else None,
        "token_usage": response.get("usage") if isinstance(response, dict) else None,
    }


def _preflight_model(adapter: Any, model: str, request_timeout: float) -> None:
    response = adapter.client.models.list(timeout=min(request_timeout, 5.0))
    available = [entry.id for entry in response.data]
    if model not in available:
        raise RuntimeError(
            f"MODEL={model!r} is absent from /models; available model ids: {available}"
        )
    print(f"[functionchat] preflight OK: MODEL={model}")


def _metadata(args: argparse.Namespace, adapter: Any, dataset: str) -> Dict[str, Any]:
    return {
        "timestamp": datetime.now().isoformat(),
        "model": args.model,
        "dataset": dataset,
        "request_timeout": args.request_timeout,
        "task_timeout": args.task_timeout,
        "max_retries": args.max_retries,
        "max_tokens": args.max_tokens,
        "native_tool_calling": args.native_tool_calling,
        "sdk_max_retries": adapter.sdk_max_retries,
        "openai_sdk_version": adapter.openai_sdk_version,
    }


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


def _safe_model_name(model: str) -> str:
    return model.replace("/", "_").replace("-", "_").replace(":", "_")


def _results_model_dir_name(base_dir: Path, model: str) -> str:
    """이미 있는 모델 디렉토리의 **실제 표기**를 재사용한다.

    문자열 치환만 하면 macOS 에서는 대소문자를 무시해 드러나지 않지만, 리눅스에서는
    ``results/google_gemma_4_26b_a4b_it`` 와 ``results/google_gemma_4_26B_A4B_it`` 가
    서로 다른 디렉토리가 되어 한 런의 산출물이 둘로 갈린다. 이 저장소에는 두 표기가
    모두 git 에 들어 있고, multimodal 트랙에서 리눅스로 실증한 결함이다.
    """

    requested = _safe_model_name(model)
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


def _timestamp(base_dir: Path) -> str:
    value = os.environ.get("EVAL_TIMESTAMP")
    if value:
        return value
    session_file = base_dir / ".eval_session"
    if session_file.is_file():
        value = session_file.read_text(encoding="utf-8").strip()
    return value or datetime.now().strftime("%Y%m%d_%H%M%S")


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument(
        "--base-url", default="http://172.16.1.81:18090/v1/chat/completions"
    )
    parser.add_argument("--track-name", default="functionchat")
    parser.add_argument("--request-timeout", type=float, default=60.0)
    parser.add_argument("--task-timeout", type=float, default=120.0)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--max-tokens", type=int, default=16384)
    parser.add_argument(
        "--native-tool-calling",
        action="store_true",
        default=_env_flag("AGENT_NATIVE_TOOL_CALLING"),
    )
    return parser.parse_args(argv)


def _validate_args(args: argparse.Namespace) -> None:
    if args.request_timeout <= 0 or args.task_timeout <= 0:
        raise ValueError("request/task timeouts must be positive")
    if args.task_timeout <= args.request_timeout:
        raise ValueError("task timeout must be greater than request timeout")
    if args.max_retries < 1:
        raise ValueError("max retries must be at least 1")
    if args.max_tokens < 1:
        raise ValueError("max tokens must be at least 1")


def main(argv: Optional[List[str]] = None) -> int:
    try:
        args = parse_args(argv)
        _validate_args(args)
        base_dir = Path(
            os.environ.get("MODEL_TEST_BASE") or Path(__file__).resolve().parents[3]
        ).resolve()
        os.environ.setdefault("MODEL_TEST_BASE", str(base_dir))
        bench_dir = base_dir / "data" / "FunctionChat-Bench"
        data_dir = bench_dir / "data"
        if not data_dir.is_dir():
            raise FileNotFoundError(f"FunctionChat-Bench data not found: {data_dir}")

        adapter_class = load_shared_adapter(base_dir)
        adapter = adapter_class(
            args.model,
            base_url=args.base_url,
            timeout=args.request_timeout,
            max_tokens=args.max_tokens,
            temperature=0.0,
            native_tool_calling=args.native_tool_calling,
        )
        _preflight_model(adapter, args.model, args.request_timeout)

        system_prompt = (data_dir / "system_prompt.txt").read_text(encoding="utf-8").strip()
        datasets = {
            "singlecall": expand_singlecall(
                data_dir / "FunctionChat-Singlecall.jsonl", system_prompt
            ),
            "call_decision": expand_call_decision(
                data_dir / "FunctionChat-CallDecision.jsonl"
            ),
            "dialog": expand_dialog(
                data_dir / "FunctionChat-Dialog.jsonl", system_prompt
            ),
        }
        timestamp = _timestamp(base_dir)
        results_dir = (
            base_dir
            / "results"
            / _results_model_dir_name(base_dir, args.model)
            / timestamp
            / "language"
            / args.track_name
        )

        raw_outputs: Dict[str, Dict[str, Any]] = {}
        for dataset, items in datasets.items():
            before_unparsed = adapter.unparsed_tool_call_candidates
            results = []
            for index, item in enumerate(items, start=1):
                # call 이든 아니든 **호출은 한다.** type_of_output 은 exact-match
                # 채점 대상인지만 가른다 — 판정 계층이 쓸 응답은 어느 쪽이든 남긴다.
                result = run_item(
                    adapter,
                    item,
                    args.task_timeout,
                    args.max_retries,
                    evaluation_status=(
                        "measured" if item["type_of_output"] == CALL else "not_measured"
                    ),
                )
                results.append(result)
                if index % 25 == 0 or index == len(items):
                    print(f"[functionchat] {dataset}: {index}/{len(items)}")

            metadata = _metadata(args, adapter, dataset)
            measured = sum(item["type_of_output"] == CALL for item in items)
            metadata.update(
                {
                    "total_items": len(items),
                    "measured_items": measured,
                    "not_measured_items": len(items) - measured,
                    "unparsed_tool_call_candidates": (
                        adapter.unparsed_tool_call_candidates - before_unparsed
                    ),
                }
            )
            raw_outputs[dataset] = {"metadata": metadata, "results": results}

        # 모든 dataset이 끝난 뒤 기록해 interrupt 시 partial run을 완전 run처럼 보이지 않게 한다.
        for dataset, raw in raw_outputs.items():
            _write_atomic(results_dir / f"{dataset}.json", raw)

        decision_types = Counter(
            item["type_of_output"] for item in datasets["call_decision"]
        )
        # dialog 은 **턴 단위**로 평가한다 (상류 payload_creator.py 도 turns 를 순회).
        # 시나리오 수(45)로 세면 판정 필요 항목이 130 대신 45 로 집계돼 커버리지가
        # 어긋난다 — 2026-08-23 에 total_items 가 551 로 찍혔고 실제는 636 이었다.
        dialog_scenarios = len(_load_jsonl(data_dir / "FunctionChat-Dialog.jsonl"))
        dialog_types = Counter(item["type_of_output"] for item in datasets["dialog"])
        coverage = {
            "source": {
                "repository": "kakao/FunctionChat-Bench",
                "commit": SOURCE_COMMIT,
            },
            "datasets": {
                "singlecall": {
                    "source_lines": 25,
                    "expanded_items": len(datasets["singlecall"]),
                    "measured_items": len(datasets["singlecall"]),
                },
                "call_decision": {
                    "source_lines": len(datasets["call_decision"]),
                    "measured_items": decision_types[CALL],
                },
                "dialog": {
                    "source_records": dialog_scenarios,
                    "expanded_items": len(datasets["dialog"]),
                    "measured_items": dialog_types[CALL],
                },
            },
            "not_measured": {
                "call_decision": {
                    "relevance": decision_types["relevance"],
                    "slot": decision_types["slot"],
                },
                # 판정이 필요한 턴을 유형별로 적는다. multi_turn 이라는 뭉뚱그린 이름으로
                # 시나리오 수를 적던 것을 바로잡았다.
                "dialog": {
                    key: dialog_types[key]
                    for key in sorted(dialog_types)
                    if key != CALL
                },
            },
        }
        _write_atomic(results_dir / "coverage.json", coverage)
        print(f"[functionchat] raw artifacts written to {results_dir}")
        return 0
    except Exception as exc:
        print(f"[functionchat] ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
