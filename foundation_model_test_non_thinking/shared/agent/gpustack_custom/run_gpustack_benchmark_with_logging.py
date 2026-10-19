"""
Ko-AgentBench 데이터셋 기반 벤치마크 실행 및 Tool Call 로깅 스크립트

data 폴더의 L1~L7 데이터셋을 로드하여 각 질문(instruction)을 실행하고,
사용된 tool call 정보를 상세하게 기록합니다.
"""

import os
import argparse
import json
import glob
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional, Type, Dict
try:
    from dotenv import load_dotenv  # provided by python-dotenv
except Exception:
    def load_dotenv(*args, **kwargs):  # no-op fallback if package not available
        return False

from bench.tools.tool_registry import ToolRegistry
from bench.adapters.openai_compat_adapter import OpenAICompatAdapter
from bench.runner import BenchmarkRunner
from bench.tools.base_api import BaseTool
from bench.models import MODEL_IDS
from bench.tools.tool_catalog import resolve_tool_classes, TOOL_CATALOG
from bench.config import set_cache_mode
from runner_timeout_config import (
    TimeoutConfigurationError,
    add_timeout_arguments,
    build_adapter_config,
    validate_timeouts,
)
from result_observability import (
    build_observability_metadata,
    completion_latency_from_task,
    finish_reason_fields,
    result_fields, token_usage_fields, simplified_tool_calls, final_response, conversation_fields,
    result_statistics, tool_usage_statistics, assemble_log_data, write_result_file,
)

# Import API keys from secrets
from configs.secrets import (
    AZURE_API_KEY, 
    AZURE_API_BASE, 
    AZURE_API_VERSION,
    ANTHROPIC_API_KEY,
    GEMINI_API_KEY,
    OPENROUTER_API_KEY,
    OPENROUTER_APP_URL,
    OPENROUTER_APP_TITLE,
)


# gpustack_custom은 외부 배치 코드라 공용 import 불가 — 같은 본문 유지.
def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes")



def load_benchmark_datasets(data_dir: str = "bench/tasks") -> Dict[str, List[Dict]]:
    """Load benchmark level files and print per-file status."""
    datasets = {}
    json_files = sorted(glob.glob(os.path.join(data_dir, "L*.json")))
    
    for filepath in json_files:
        level_name = Path(filepath).stem  # L1, L2, etc.
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                datasets[level_name] = data
                print(f"[OK] Loaded {level_name}: {len(data)} tasks")
        except Exception as e:
            print(f"[ERROR] Failed to load {filepath}: {e}")
    
    return datasets


def create_tool_registry(tool_classes: Optional[List[Type[BaseTool]]] = None) -> ToolRegistry:
    """Create a ToolRegistry and register provided tool classes."""
    registry = ToolRegistry()
    if tool_classes:
        for tool_class in tool_classes:
            registry.register_tool(tool_class)
    return registry


def golden_tools(task):
    """Collect golden tool names in first-seen order."""
    tools_needed = []

    # First, try golden_action (L1-L6)
    if "golden_action" in task:
        for action in task["golden_action"]:
            tool_name = action.get("tool", "")
            if tool_name and tool_name not in tools_needed:
                tools_needed.append(tool_name)

    return tools_needed


def conversation_tools(task, tools_needed):
    """Yield new conversation tools lazily without mutating the input."""
    seen = list(tools_needed)
    conversation = task["conversation_tracking"]
    for turn in conversation.get("turns", []):
        # L7 format: turn.actions (list)
        if "actions" in turn:
            for action in turn.get("actions", []):
                tool_name = action.get("tool", "")
                if tool_name and tool_name not in seen:
                    seen.append(tool_name)
                    yield "actions", tool_name

        # L6 format: turn.action (single object)
        if "action" in turn:
            action = turn.get("action", {})
            tool_name = action.get("tool", "")
            if tool_name and tool_name not in seen:
                seen.append(tool_name)
                yield "action", tool_name


def exposed_tools_for_task(task, expected_tools):
    """Append declared and fallback tools while retaining golden tools."""
    exposed_tools = list(expected_tools)

    # L2 source tasks declare distractors in available_tools. Preserve those
    # candidates without dropping any golden or conversation-derived tools.
    for tool_name in task.get("available_tools") or []:
        if tool_name and tool_name not in exposed_tools:
            exposed_tools.append(tool_name)

    # L5 fallback tools are registered and may be exposed after a failed call.
    for fallback_option in task.get("fallback_options") or []:
        if not isinstance(fallback_option, dict):
            continue
        tool_name = fallback_option.get("tool")
        if tool_name and tool_name not in exposed_tools:
            exposed_tools.append(tool_name)

    return exposed_tools


def convert_task(task, expected_tools, exposed_tools):
    """Convert one dataset item, preserving field order and shared tool lists."""
    conversation_tracking = task.get("conversation_tracking") or {}
    evaluation_context = conversation_tracking.get("evaluation_context") or {}

    converted_task = {
        "id": task.get("task_id", "unknown"),
        "description": task.get("instruction", ""),
        "expected_output": task.get("resp_schema", {}),
        "available_tools": exposed_tools,
        # keep backward-compat with runner that expects 'tools'
        "tools": exposed_tools,
        "expected_tools": expected_tools,
        "level": task.get("task_level", 0),
        "category": task.get("task_category", "unknown"),
        "golden_action": task.get("golden_action", []),
        "golden_fields": task.get("golden_fields", []),
        "context_tests": evaluation_context.get("context_tests", []),
        "long_term_tests": task.get("long_term_tests", []),
        "conversation_tracking": task.get("conversation_tracking"),
        "arg_schema": task.get("arg_schema", {}),
        # Pass through evaluation helpers if present
        "minimum_steps": task.get("minimum_steps"),
        "data_flow": task.get("data_flow", []),
        "error_injection": task.get("error_injection"),
        "fallback_options": task.get("fallback_options", [])
    }
    return converted_task


def required_tools(converted_tasks):
    """Collect tools required by a dataset in first-seen order."""
    all_required_tools = []
    for task in converted_tasks:
        # Add main tools
        for tool in task.get("available_tools", []):
            if tool not in all_required_tools:
                all_required_tools.append(tool)

        # Add fallback tools for L5 tasks
        if task.get("fallback_options"):
            for fallback_option in task["fallback_options"]:
                tool_name = fallback_option.get("tool")
                if tool_name and tool_name not in all_required_tools:
                    all_required_tools.append(tool_name)

    return all_required_tools


def convert_dataset_to_tasks(dataset_tasks: List[Dict]) -> List[Dict]:
    """Convert tasks and emit legacy tool discovery diagnostics."""
    converted_tasks = []
    if isinstance(dataset_tasks, list) and len(dataset_tasks) > 0 and isinstance(dataset_tasks[0], list):
        dataset_tasks = dataset_tasks[0]
    for task in dataset_tasks:
        if not isinstance(task, dict):
            print(f"[WARNING] Skipping non-dict task: {type(task)}")
            continue
        tools_needed = golden_tools(task)
        if "conversation_tracking" in task:
            print(f"[DEBUG] Processing conversation_tracking for task: {task.get('task_id')}")
            for origin, tool_name in conversation_tools(task, tools_needed):
                tools_needed.append(tool_name)
                print(f"  [OK] Found tool in turn.{origin}: {tool_name}")
        expected_tools = list(tools_needed)
        exposed_tools = exposed_tools_for_task(task, expected_tools)
        print(f"  [INFO] Task {task.get('task_id')}: exposed_tools = {exposed_tools}")
        converted_tasks.append(convert_task(task, expected_tools, exposed_tools))
    return converted_tasks


def _resolve_multiturn_mode(args: argparse.Namespace) -> str:
    """Resolve seed replay or the opt-in full rollout mode."""
    return "full_rollout" if getattr(args, "full_rollout", False) else "seed_replay"


def simplify_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """Coordinate ordered result fields and observability hooks."""
    simplified = result_fields(result)
    simplified.update(token_usage_fields(result))
    simplified["completion_latency"] = completion_latency_from_task(result)
    simplified.update(finish_reason_fields(result))
    simplified["tool_calls"] = simplified_tool_calls(result)
    simplified["final_response"] = final_response(result)
    simplified.update(conversation_fields(result))
    return simplified


def _decoding_provenance(max_tokens, temperature):
    """Record explicit requested decoding settings and their effective values."""

    try:
        from serving.constraints import effective_decoding
    except Exception:
        try:
            _shared = Path(__file__).resolve().parents[2]
            if str(_shared) not in sys.path:
                sys.path.insert(0, str(_shared))
            from serving.constraints import effective_decoding
        except Exception:
            return {"available": False}
    requested, effective, constraints = effective_decoding(
        temperature=temperature, max_tokens=max_tokens, seed=None
    )
    removed = list(constraints.get("removed_parameters") or [])
    return {
        "available": True,
        "requested": requested,
        "effective": effective,
        "constraints": constraints,
        # **true 가 결정론을 뜻하지 않는다.** temperature=0 을 보냈어도 배치 구성,
        # MoE 라우팅, 부동소수점 비결합성으로 결과는 달라질 수 있다. 재현을
        # 부정하는 근거만 싣는다.
        "sampling_controls_removed": "temperature" in removed,
    }


def resolve_results_model_dir(model_name: str, output_dir: Optional[str] = None) -> Path:
    """Resolve the result root and model spelling before evaluation or session writes."""
    if output_dir is None:
        env_base = os.environ.get("MODEL_TEST_BASE")
        base_dir = Path(env_base).resolve() if env_base else Path(__file__).resolve().parent.parent.parent
        output_dir = str(base_dir / "results")
    root = Path(output_dir)
    requested = model_name.replace("/", "_").replace("-", "_").replace(":", "_")
    matches = sorted(p.name for p in root.iterdir()
                     if p.is_dir() and p.name.casefold() == requested.casefold()) if root.is_dir() else []
    if len(matches) > 1:
        raise ValueError(f"case-fold ambiguous results model directory for {requested!r}: {matches}")
    return root / (matches[0] if matches else requested)


def save_detailed_results(
    results: List[Dict[str, Any]],
    model_name: str,
    level_name: str,
    output_dir: Optional[str] = None,
    run_timestamp: str = None,
    track_name: str = "agent",
    native_tool_calling: bool = False,
    unparsed_tool_call_candidates: int = 0,
    *,
    request_timeout: float,
    task_timeout: float,
    max_tokens: int,
    temperature: float,
    max_retries: int,
    openai_sdk_version: str,
    sdk_max_retries: int,
    resolved_model_dir: Optional[Path] = None,
) -> str:
    """Simplify, aggregate and write detailed results to the resolved output path."""
    if run_timestamp is None:
        run_timestamp = os.environ.get("EVAL_TIMESTAMP") or datetime.now().strftime("%Y%m%d_%H%M%S")

    result_path = (resolved_model_dir if resolved_model_dir is not None else
                   resolve_results_model_dir(model_name, output_dir))
    result_path = result_path / run_timestamp / "language" / track_name
    result_path.mkdir(parents=True, exist_ok=True)

    filename = f"{level_name}.json"
    filepath = result_path / filename
    
    # Simplify and flatten results
    simplified_results = [simplify_result(r) for r in results]
    
    statistics = result_statistics(simplified_results)
    observability_metadata = build_observability_metadata(simplified_results)
    tool_usage_stats = tool_usage_statistics(simplified_results)
    metadata = {
        "timestamp": datetime.now().isoformat(),
        "model": model_name,
        "level": level_name,
        "native_tool_calling": native_tool_calling,
        "unparsed_tool_call_candidates": unparsed_tool_call_candidates,
        "request_timeout": request_timeout,
        "task_timeout": task_timeout,
        # 요청값이다. 실제로 보낸 값은 decoding.effective 를 봐야 한다 —
        # 서빙 제약이 이 값을 잘라낼 수 있다.
        "max_tokens": max_tokens,
        "decoding": _decoding_provenance(max_tokens, temperature),
        "max_retries": max_retries,
        "openai_sdk_version": openai_sdk_version,
        "sdk_max_retries": sdk_max_retries,
    }
    log_data = assemble_log_data(metadata, statistics, observability_metadata,
                                 tool_usage_stats, simplified_results)
    return write_result_file(filepath, log_data)


def _create_components(converted_tasks, model_name, adapter_config, max_steps, timeout, max_retries, multiturn_mode, *, print=print):
    """Resolve tools, print registry details and construct the adapter and runner."""
    all_required_tools = required_tools(converted_tasks)
    print(f"Required tools: {all_required_tools}")

    # 입력된 이름을 그대로 사용
    print(f"Tools: {all_required_tools}")

    # Resolve and register tools
    tool_classes = resolve_tool_classes(all_required_tools)
    missing_tools = [t for t in all_required_tools if t not in TOOL_CATALOG]
    if missing_tools:
        print(f"[WARNING] Missing tools in catalog: {missing_tools}")

    # Setup components
    registry = create_tool_registry(tool_classes)

    # DEBUG: Check registered tools and their schemas
    print(f"\n[DEBUG] Registered tools in registry:")
    registered_tool_names = registry.get_available_tools()
    print(f"  Tool names: {registered_tool_names}")

    if registered_tool_names:
        print(f"\n  Tool schemas:")
        for tool_name in registered_tool_names[:3]:  # Show first 3
            tool = registry.get_tool(tool_name)
            if tool:
                schema = tool.get_schema()
                print(f"    - {tool_name}:")
                print(f"      Schema keys: {list(schema.keys())}")
                if 'function' in schema:
                    print(f"      Function name: {schema['function'].get('name')}")
                    print(f"      Description: {schema['function'].get('description')[:50]}...")
    else:
        print("  [WARNING] No tools registered!")

    # Always use OpenAICompatAdapter for OpenAI-compatible endpoint
    print(f"\n[API] Using OpenAICompatAdapter for OpenAI-compatible endpoint")
    # request_timeout(요청당) → 어댑터의 timeout 키로 변환.
    # 함수 인자 timeout 은 태스크 예산이라 이름이 겹치면 안 된다.
    adapter_config = dict(adapter_config)
    if "request_timeout" in adapter_config:
        adapter_config["timeout"] = adapter_config.pop("request_timeout")
    adapter = OpenAICompatAdapter(model_name, **adapter_config)
    native_tool_calling = bool(adapter_config.get("native_tool_calling", False))

    runner = BenchmarkRunner(
        adapter,
        registry,
        max_steps=max_steps,
        timeout=timeout,
        max_retries=max_retries,
        multiturn_mode=multiturn_mode,
    )

    return adapter, runner, native_tool_calling


def _print_task(task, index, total, repetitions, *, print=print):
    """Print task context and repetition information."""
    print(f"\n{'─'*80}")
    print(f"Task {index}/{total}: {task['id']}")
    print(f"Level: {task['level']} | Category: {task['category']}")
    print(f"Instruction: {task['description']}")
    print(f"Expected tools: {task['expected_tools']}")
    print(f"Exposed tools: {task['available_tools']}")

    # Log multi-turn conversation context if present
    if task.get("conversation_tracking") and isinstance(task["conversation_tracking"].get("turns"), list):
        turns = task["conversation_tracking"]["turns"]
        valid_turns = [t for t in turns if t.get("role") in ("user", "assistant") and t.get("content")]
        print(f"\n[MULTI-TURN] Multi-turn conversation context:")
        print(f"   Total turns to seed: {len(valid_turns)}")
        for idx, turn in enumerate(valid_turns, 1):
            role = turn.get("role", "unknown")
            content = turn.get("content", "")
            content_preview = content[:100] + "..." if len(content) > 100 else content
            print(f"   Turn {idx} [{role}]: {content_preview}")

            # Log any tool actions in this turn (for reference)
            if turn.get("actions"):
                for action in turn["actions"]:
                    tool_name = action.get("tool", "unknown")
                    print(f"      [TOOL] Expected tool: {tool_name}")

    # Log repetitions info
    if repetitions > 1:
        print(f"\n[REPETITIONS] Running task {repetitions} times for pass@k metric")

    print(f"{'─'*80}")


def _run_repetitions(task, repetitions, adapter, runner, *, print=print):
    """Run repetitions, updating adapter.seed only under the legacy rule."""
    # Run task with repetitions
    repetition_results = []
    main_result = None

    for rep in range(repetitions):
        if repetitions > 1:
            print(f"\n[Repetition {rep + 1}/{repetitions}]")
            # 매 반복마다 seed 변동 (temp>0 일 때 진짜 다양성 보장)
            # vLLM/서빙 설정에 따라 같은 seed 면 동일 응답 가능 → seed=rep 로 강제 변동
            if hasattr(adapter, "seed") and getattr(adapter, "temperature", 0.0) > 0:
                adapter.seed = 1000 + rep

        result = runner.run_task(task)

        # Store repetition success status
        repetition_results.append(result.get('success', False))

        # Use first run as main result
        if rep == 0:
            main_result = result

    return main_result, repetition_results


def _merge_task_result(result, task, repetitions, repetition_results):
    """Mutate the first result with original task and repetition fields."""
    # Add original task information
    result['task_id'] = task['id']
    result['instruction'] = task['description']
    result['level'] = task['level']
    result['category'] = task['category']
    result['expected_tools'] = task['expected_tools']
    result['exposed_tools'] = task['available_tools']
    result['golden_action'] = task['golden_action']
    result['golden_fields'] = task['golden_fields']
    result['context_tests'] = task['context_tests']
    result['long_term_tests'] = task['long_term_tests']
    # Add repetition results for pass@k metric
    result['repetitions'] = repetitions
    result['repetition_results'] = repetition_results
    # Include dataset guidance fields for analysis
    if 'minimum_steps' in task:
        result['minimum_steps'] = task.get('minimum_steps')
    if 'data_flow' in task:
        result['data_flow'] = task.get('data_flow', [])
    if 'error_injection' in task:
        result['error_injection'] = task.get('error_injection')
    # Include fallback_options for L5 tasks
    if 'fallback_options' in task:
        result['fallback_options'] = task.get('fallback_options')
    # Include resp_schema and arg_schema for evaluation
    if 'expected_output' in task:
        result['resp_schema'] = task.get('expected_output', {})
    if 'arg_schema' in task:
        result['arg_schema'] = task.get('arg_schema', {})


def _print_task_result(result, repetitions, repetition_results, *, print=print):
    """Print result, tool calls and conversation previews."""
    # Print summary
    print(f"\n[RESULT] Success: {result['success']}")
    if repetitions > 1:
        success_count = sum(repetition_results)
        print(f"  Pass@{repetitions}: {success_count}/{repetitions} ({success_count/repetitions*100:.1f}%)")
    print(f"  Execution time: {result['execution_time']:.2f}s")
    print(f"  Steps taken: {result['steps_taken']}")

    # Print tool call details
    tool_calls = result.get('tool_calls', [])
    if tool_calls:
        print(f"  Tool calls: {len(tool_calls)}")
        for inv in tool_calls:
            print(f"    • Step {inv.get('step')}: {inv.get('tool_name')}")
            print(f"      Args: {inv.get('arguments')}")
            print(f"      Success: {inv.get('success')}")
            if inv.get('error'):
                print(f"      Error: {inv.get('error')}")
    else:
        print(f"  Tool calls: 0 (no tools used)")

    # Print conversation summary for multi-turn tasks
    if result.get('result') and result['result'].get('conversation'):
        conversation = result['result']['conversation']
        print(f"\n  [CONVERSATION] Conversation summary:")
        print(f"     Total messages: {len(conversation)}")

        # Show last few messages
        last_messages = conversation[-3:] if len(conversation) > 3 else conversation
        for msg in last_messages:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            if content:
                preview = content[:80] + "..." if len(content) > 80 else content
                print(f"     [{role}]: {preview}")

    if result.get('result') and result['result'].get('final_response'):
        response = result['result']['final_response']
        preview = response[:200] + "..." if len(response) > 200 else response
        print(f"  Response: {preview}")


def _execute_task(task, repetitions, adapter, runner, all_results, *, print=print):
    """Execute one task and append success or failure records to all_results."""
    try:
        result, repetition_results = _run_repetitions(task, repetitions, adapter, runner, print=print)
        _merge_task_result(result, task, repetitions, repetition_results)
        all_results.append(result)
        _print_task_result(result, repetitions, repetition_results, print=print)
    except Exception as e:
        print(f"\n[ERROR] Execution failed: {e}")
        all_results.append({
            "task_id": task.get('id', 'unknown'),
            "instruction": task.get('description', ''),
            "level": task.get('level', 0),
            "category": task.get('category', 'unknown'),
            "expected_tools": task.get('expected_tools', []),
            "exposed_tools": task.get('available_tools', []),
            "golden_action": task.get('golden_action', []),
            "golden_fields": task.get('golden_fields', []),
            "context_tests": task.get('context_tests', []),
            "long_term_tests": task.get('long_term_tests', []),
            "minimum_steps": task.get('minimum_steps'),
            "data_flow": task.get('data_flow', []),
            "repetitions": repetitions,
            "repetition_results": [False] * repetitions,
            "success": False,
            "error": str(e),
            "execution_time": 0,
            "steps_taken": 0,
            "tool_invocations": []
        })


def run_benchmark_on_dataset(
    level_name: str,
    tasks: List[Dict],
    model_name: str = "gpt-4.1",
    use_local: bool = False,
    max_steps: int = 10,
    timeout: int = 60,
    max_retries: int = 2,
    save_logs: bool = True,
    log_dir: Optional[str] = None,
    run_timestamp: str = None,
    repetitions: int = 1,
    multiturn_mode: str = "seed_replay",
    track_name: str = "agent",
    resolved_model_dir: Optional[Path] = None,
    **adapter_config: Any
) -> List[Dict[str, Any]]:
    """Coordinate conversion, task execution and optional dataset persistence."""
    print(f"\n{'='*80}")
    print(f"Running Benchmark: {level_name} ({len(tasks)} tasks)")
    print(f"Model: {model_name}")
    print(f"{'='*80}\n")
    
    # Debug: Check tasks type
    print(f"DEBUG: tasks type = {type(tasks)}")
    if isinstance(tasks, list) and len(tasks) > 0:
        print(f"DEBUG: first task type = {type(tasks[0])}")
    
    # Direct callers with log_dir must also fail before any task is evaluated.
    if resolved_model_dir is None:
        resolved_model_dir = resolve_results_model_dir(model_name, log_dir)

    # Convert dataset format to runner format (always use full set)
    converted_tasks = convert_dataset_to_tasks(tasks)
    
    adapter, runner, native_tool_calling = _create_components(
        converted_tasks, model_name, adapter_config, max_steps, timeout, max_retries, multiturn_mode)
    all_results = []
    for i, task in enumerate(converted_tasks, 1):
        _print_task(task, i, len(converted_tasks), repetitions)
        _execute_task(task, repetitions, adapter, runner, all_results)
    if save_logs and all_results:
        try:
            filepath = save_detailed_results(
                all_results,
                model_name,
                level_name,
                log_dir,
                run_timestamp,
                track_name=track_name,
                native_tool_calling=native_tool_calling,
                unparsed_tool_call_candidates=adapter.unparsed_tool_call_candidates,
                request_timeout=adapter.timeout,
                task_timeout=runner.timeout,
                max_tokens=adapter.max_tokens,
                temperature=adapter.temperature,
                max_retries=runner.max_retries,
                openai_sdk_version=adapter.openai_sdk_version,
                sdk_max_retries=adapter.sdk_max_retries,
                resolved_model_dir=resolved_model_dir,
            )
            print(f"\n{'='*80}")
            print(f"Results saved to: {filepath}")
            print(f"{'='*80}\n")
        except Exception as e:
            print(f"\n[ERROR] Failed to save results: {e}\n")
    return all_results


def _parse_args():
    """Parse agent benchmark command-line arguments."""
    parser = argparse.ArgumentParser(description="Ko-AgentBench runner with tool-call logging")
    parser.add_argument("--levels", type=str, default=None,
                        help="Comma-separated levels to run (e.g., L6,L7). Default: all detected")
    # removed --limit: always run full level
    parser.add_argument("--max-steps", type=int, default=10,
                        help="Maximum steps per task")
    add_timeout_arguments(parser)
    parser.add_argument(
        "--full-rollout",
        action="store_true",
        help="(L6/L7) Execute full multi-turn rollout (call the model for every user turn). "
             "Default is seed replay (only call the model on the evaluation turn).",
    )
    parser.add_argument("--no-save-logs", action="store_true",
                        help="Do not save JSON logs to disk")
    parser.add_argument("--model", type=str, default=None,
                        help="Explicit model id (overrides auto selection)")
    parser.add_argument(
        "--base_url",
        type=str,
        default=None,
        help=(
            "OpenAI-compatible base URL or chat-completions endpoint. "
            "Examples: http://host:port/v1 OR http://host:port/v1/chat/completions"
        ),
    )
    parser.add_argument("--use-local", action="store_true",
                        help="Use local transformers inference instead of API")
    parser.add_argument("--quantization", type=str, default=None, choices=['4bit', '8bit'],
                        help="Quantization method for local models (4bit or 8bit)")
    parser.add_argument("--device", type=str, default="auto",
                        help="Device for local inference (cuda, cpu, auto)")
    parser.add_argument("--dtype", type=str, default="auto",
                        choices=['auto', 'float16', 'bfloat16', 'float32', 'fp16', 'bf16', 'fp32'],
                        help="Torch dtype for local models")
    parser.add_argument("--cache-mode", type=str, default="read",
                        choices=['read', 'write'],
                        help="Cache mode for API calls: 'read' = use cached responses only (no real API calls), 'write' = call real APIs and cache results (default: read)")
    parser.add_argument("--repetitions", type=int, default=1,
                        help="Number of repetitions for each task to measure pass@k metric (default: 1)")

    # GPT-5 reasoning control arguments
    parser.add_argument("--effort", type=str, default="low",
                        choices=['low', 'medium', 'high'],
                        help="Reasoning effort for GPT-5 (low, medium, high, default: low)")
    parser.add_argument("--max-completion-tokens", type=int, default=1024,
                        help="Maximum completion tokens for GPT-5 (default: 1024)")

    # vLLM-specific arguments
    parser.add_argument("--tensor-parallel-size", type=int, default=1,
                        help="Number of GPUs for tensor parallelism (vLLM only, default: 1)")
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.9,
                        help="GPU memory utilization for vLLM (0.0-1.0, default: 0.9)")
    parser.add_argument("--max-model-len", type=int, default=None,
                        help="Maximum model context length for vLLM (default: auto-detect)")

    # 결과 트랙 분기 + 평가 결정성 제어
    parser.add_argument("--track-name", type=str, default="agent",
                        help="결과 저장 subfolder under language/ (default: 'agent'). "
                             "pass@k 보조 트랙은 'agent_passk' 등으로 override.")
    parser.add_argument("--temperature", type=float, default=None,
                        help="모델 sampling temperature (default: None → adapter default 0.0). "
                             "pass@k 트랙은 0.3~0.7 권장.")
    parser.add_argument("--native-tool-calling", action="store_true",
                        default=_env_flag("AGENT_NATIVE_TOOL_CALLING"),
                        help="서버의 OpenAI-compatible tools 파라미터를 직접 사용한다. "
                             "서버가 --enable-auto-tool-choice 로 떠 있어야 함. "
                             "미지원 서버에서 켜면 400 응답이 날 수 있음. "
                             "기본값은 AGENT_NATIVE_TOOL_CALLING env (1/true/yes).")

    return parser.parse_args()


def _prepare_environment(args, environ, *, print=print):
    """Configure logging, load credentials and update the supplied environment."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()  # Console output
        ]
    )

    # Load environment variables (must run before OpenAICompatAdapter reads OPENAI_API_KEY)
    load_dotenv()

    if args.base_url and not environ.get("OPENAI_API_KEY"):
        print(
            "[WARNING] OPENAI_API_KEY is not set. GPUStack / OpenAI-compatible "
            "servers often require it (Bearer). Set it in .env or export OPENAI_API_KEY=..."
        )

    # Set API keys environment variables if available from secrets
    if AZURE_API_KEY:
        environ['AZURE_API_KEY'] = AZURE_API_KEY
    if AZURE_API_BASE:
        environ['AZURE_API_BASE'] = AZURE_API_BASE
    if AZURE_API_VERSION:
        environ['AZURE_API_VERSION'] = AZURE_API_VERSION
    if ANTHROPIC_API_KEY:
        environ['ANTHROPIC_API_KEY'] = ANTHROPIC_API_KEY
    if GEMINI_API_KEY:
        environ['GEMINI_API_KEY'] = GEMINI_API_KEY
    if OPENROUTER_API_KEY:
        environ['OPENROUTER_API_KEY'] = OPENROUTER_API_KEY
    if OPENROUTER_APP_URL:
        environ.setdefault('OPENROUTER_APP_URL', OPENROUTER_APP_URL)
    if OPENROUTER_APP_TITLE:
        environ.setdefault('OPENROUTER_APP_TITLE', OPENROUTER_APP_TITLE)

    # Check API keys (include Azure/Google for better provider detection)
    provider_keys = [
        "HUGGINGFACE_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GROQ_API_KEY",
        "AZURE_API_KEY",
        "GEMINI_API_KEY",
        "OPENROUTER_API_KEY",
    ]
    found_keys = [k for k in provider_keys if environ.get(k)]
    if not found_keys:
        print("[WARNING] No LLM API keys found in environment")
    else:
        print(f"[OK] Found API keys: {found_keys}")


def _provider_ready(model_id: str, environ) -> bool:
    """Return True if the provider for model_id has required env keys."""
    # Model id format: "<provider>/<model_name>"
    if "/" not in model_id:
        return False
    provider = model_id.split("/", 1)[0].lower()
    if provider == "azure":
        return bool(environ.get("AZURE_API_KEY") and environ.get("AZURE_API_BASE") and environ.get("AZURE_API_VERSION"))
    if provider == "openai":
        return bool(environ.get("OPENAI_API_KEY"))
    if provider == "anthropic":
        return bool(environ.get("ANTHROPIC_API_KEY"))
    if provider == "groq":
        return bool(environ.get("GROQ_API_KEY"))
    if provider == "gemini":
        return bool(environ.get("GEMINI_API_KEY"))
    if provider == "openrouter":
        return bool(environ.get("OPENROUTER_API_KEY"))
    if provider == "huggingface":
        return bool(environ.get("HUGGINGFACE_API_KEY"))
    return False

def _select_model(args, environ, *, print=print):
    """Select a model using credentials and print local inference settings."""
    selected_model = None
    if MODEL_IDS:
        # Prefer the first model in MODEL_IDS that matches available keys
        for m in MODEL_IDS:
            if _provider_ready(m, environ):
                selected_model = m
                break
        # Fallback: keep existing preference order if none match
        if selected_model is None:
            selected_model = MODEL_IDS[0]
            # Only warn if NOT using local inference
            if not args.use_local:
                print(
                    f"[WARNING] No provider credentials matched MODEL_IDS. Falling back to '{selected_model}'.\n"
                    f"  Tip: Set provider keys to match one of: {MODEL_IDS}"
                )
    else:
        # Final fallback
        selected_model = "openai/gpt-4.1" if environ.get("OPENAI_API_KEY") else "azure/gpt-4.1"

    # Override model from CLI if provided
    if args.model:
        selected_model = args.model
    print(f"\nSelected model: {selected_model}")

    # For local inference, model name doesn't need provider prefix
    if args.use_local:
        # Remove provider prefix if present (e.g., "huggingface/Qwen/..." -> "Qwen/...")
        if "/" in selected_model and selected_model.split("/")[0] in ["huggingface", "openai", "anthropic", "azure", "groq", "gemini", "openrouter"]:
            selected_model = "/".join(selected_model.split("/")[1:])
        print(f"Using local inference mode")
        print(f"Model: {selected_model}")
        if args.quantization:
            print(f"Quantization: {args.quantization}")
        print(f"Device: {args.device}")
        print(f"Dtype: {args.dtype}")

    return selected_model


def _build_runtime_config(args, selected_model):
    """Build adapter options while preserving CLI defaults and insertion order."""
    # Prepare adapter config for local models
    adapter_config = build_adapter_config(args)
    if args.use_local:
        adapter_config['device'] = args.device
        adapter_config['dtype'] = args.dtype
        if args.quantization:
            adapter_config['quantization'] = args.quantization

        # vLLM-specific configurations (applied when --model starts with vllm/)
        if selected_model.startswith("vllm/"):
            adapter_config['tensor_parallel_size'] = args.tensor_parallel_size
            adapter_config['gpu_memory_utilization'] = args.gpu_memory_utilization
            if args.max_model_len:
                adapter_config['max_model_len'] = args.max_model_len
        # Context management is now handled automatically by adapters
        # based on model config (max_position_embeddings, etc.)

    # GPT-5 reasoning control configuration (for all models, but only used by GPT-5)
    adapter_config['effort'] = args.effort
    adapter_config['max_completion_tokens'] = args.max_completion_tokens
    if args.base_url:
        adapter_config["base_url"] = args.base_url
    adapter_config['native_tool_calling'] = args.native_tool_calling

    # Agent 트랙: tool call + reasoning + multi-turn 고려해 max_tokens 16384 default
    # (openai_compat_adapter.py의 전역 default 8192를 override)
    adapter_config.setdefault('max_tokens', 16384)
    # temperature: 메인 평가는 0.0 (결정론적), pass@k 보조 트랙은 --temperature 0.7 등으로 override
    if args.temperature is not None:
        adapter_config['temperature'] = args.temperature
    else:
        adapter_config.setdefault('temperature', 0.0)

    return adapter_config


def _run_timestamp(environ, script_path):
    """Read or write the session file selected by environ and script_path."""
    run_timestamp = environ.get("EVAL_TIMESTAMP")
    if not run_timestamp:
        # BASE_DIR 추정: MODEL_TEST_BASE env or runtime 위치 기준
        env_base = environ.get("MODEL_TEST_BASE")
        if env_base:
            base_for_session = Path(env_base).resolve()
        else:
            # 이 파일은 install 후 <BASE>/<class>/agent/Ko-AgentBench/<this>
            base_for_session = Path(script_path).resolve().parent.parent.parent
        session_file = base_for_session / ".eval_session"
        if session_file.exists():
            try:
                run_timestamp = session_file.read_text().strip() or None
            except Exception:
                run_timestamp = None
        if not run_timestamp:
            run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            try:
                session_file.write_text(run_timestamp)
            except Exception:
                pass

    return run_timestamp


def _run_levels(args, datasets, selected_model, resolved_model_dir, run_timestamp, multiturn_mode, adapter_config, *, print=print):
    """Run selected dataset levels through the public runner hook."""
    all_level_results = {}
    # Determine which levels to run
    if args.levels:
        levels_to_run = [lvl.strip() for lvl in args.levels.split(',') if lvl.strip()]
    else:
        # Default: run all discovered levels (including multi-turn L6/L7)
        levels_to_run = sorted(list(datasets.keys()))

    for level_name in levels_to_run:
        if level_name in datasets:
            results = run_benchmark_on_dataset(
                level_name=level_name,
                tasks=datasets[level_name],
                model_name=selected_model,
                use_local=args.use_local,
                max_steps=args.max_steps,
                timeout=args.timeout,
                max_retries=args.max_retries,
                save_logs=(not args.no_save_logs),
                log_dir=str(resolved_model_dir.parent),
                resolved_model_dir=resolved_model_dir,
                run_timestamp=run_timestamp,
                repetitions=args.repetitions,
                multiturn_mode=multiturn_mode,
                track_name=args.track_name,
                **adapter_config
            )
            all_level_results[level_name] = results
        else:
            print(f"[WARNING] {level_name} not found in datasets")

    return all_level_results


def _print_overall_summary(all_level_results, *, print=print):
    """Print per-level success totals."""
    # Print overall summary
    print("\n" + "="*80)
    print("OVERALL SUMMARY")
    print("="*80)
    for level_name, results in all_level_results.items():
        total = len(results)
        success = sum(1 for r in results if r.get('success', False))
        success_rate = (success / total * 100) if total > 0 else 0
        print(f"{level_name}: {success}/{total} tasks successful ({success_rate:.1f}%)")
    print("="*80)


def main():
    """Coordinate benchmark setup, dataset runs and overall summary."""
    args = _parse_args()
    try:
        validate_timeouts(args)
    except TimeoutConfigurationError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    set_cache_mode(args.cache_mode)
    print(f"Cache mode: {args.cache_mode}")
    multiturn_mode = _resolve_multiturn_mode(args)
    print(f"Multi-turn mode: {multiturn_mode}")
    print("="*80)
    print("Ko-AgentBench Dataset Runner with Tool Call Logging")
    print("="*80)
    _prepare_environment(args, os.environ)
    print("\nLoading benchmark datasets...")
    datasets = load_benchmark_datasets("bench/tasks")
    if not datasets:
        print("[ERROR] No datasets found in bench/tasks/ directory")
        return
    print(f"\n[OK] Loaded {len(datasets)} dataset levels")
    selected_model = _select_model(args, os.environ)
    try:
        resolved_model_dir = resolve_results_model_dir(selected_model)
    except ValueError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(2)
    adapter_config = _build_runtime_config(args, selected_model)
    run_timestamp = _run_timestamp(os.environ, __file__)
    all_level_results = _run_levels(args, datasets, selected_model, resolved_model_dir,
                                    run_timestamp, multiturn_mode, adapter_config)
    _print_overall_summary(all_level_results)


if __name__ == "__main__":
    sys.exit(main())
