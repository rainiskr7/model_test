"""agent scoring 단독 실행 테스트.

패키지 import 없이 파일 경로에서 직접 로드한다.
"""

import importlib.util
import os
import sys
from pathlib import Path


SCORING_DIR = Path(__file__).resolve().parents[2] / "scoring"
TREE_ROOT = Path(__file__).resolve().parents[4]
if not os.environ.get("MODEL_TEST_BASE") and (
    TREE_ROOT / "data" / "Ko-AgentBench" / "bench" / "runner" / "metrics.py"
).is_file():
    os.environ["MODEL_TEST_BASE"] = str(TREE_ROOT)


def _load_module(name):
    path = SCORING_DIR / f"{name}.py"
    return _load_module_from_path(name, path, str(SCORING_DIR))


def _load_module_from_path(name, path, import_dir=None):
    spec = importlib.util.spec_from_file_location(f"{name}_under_test", path)
    module = importlib.util.module_from_spec(spec)
    if import_dir is not None:
        sys.path.insert(0, str(import_dir))
    try:
        spec.loader.exec_module(module)
    finally:
        if import_dir is not None:
            try:
                sys.path.remove(str(import_dir))
            except ValueError:
                pass
    return module


extra_metrics = _load_module("extra_metrics")
level_spec = _load_module("level_spec")
score_run = _load_module("score_run")
context = _load_module("context")
data_health = _load_module("data_health")
l6_context = _load_module("l6_context")


class DummyContext:
    def __init__(self, golden_action, action_trace, minimum_calls=None):
        self.task_schema = {"golden_action": golden_action}
        if minimum_calls is not None:
            self.task_schema["minimum_calls"] = minimum_calls
        self.action_trace = action_trace


class MetricContext:
    def __init__(self, task_schema, final_response):
        self.task_schema = task_schema
        self.logs = {"final_response": final_response}


def _l6_schema(tool="ToolA", fields=None, result=None, final_seed_content="seeded answer"):
    fields = fields if fields is not None else ["item.title", "item.author"]
    result = result if result is not None else {"item": {"title": "책 제목", "author": "홍길동"}}
    return {
        "task_id": "L6-field",
        "task_level": 6,
        "golden_fields": [{"tool": tool, "fields": fields}],
        "conversation_tracking": {
            "turns": [
                {"turn_number": 1, "role": "user", "content": "찾아줘"},
                {
                    "turn_number": 2,
                    "role": "assistant",
                    "content": final_seed_content,
                    "action": {"tool": tool, "args": {}, "result": result},
                },
                {"turn_number": 3, "role": "user", "content": "아까 것 다시 알려줘"},
            ]
        },
    }


def _l6_metric(fields=None, result=None, final_response="", final_seed_content="seeded answer"):
    return extra_metrics.golden_field_recall_det(
        MetricContext(
            _l6_schema(fields=fields, result=result, final_seed_content=final_seed_content),
            final_response,
        )
    )


def _assert(condition, message):
    if not condition:
        raise AssertionError(message)


def _assert_close(actual, expected, message):
    if actual is None or abs(actual - expected) > 1e-9:
        raise AssertionError(f"{message}: expected {expected}, got {actual}")



def _l7_bench_task(context_tests):
    return {
        "task_id": "L7-x",
        "task_level": 7,
        "conversation_tracking": {
            "evaluation_context": {
                "context_tests": context_tests,
            }
        },
    }



def _l2_task(task_id, tool_name):
    return {
        "task_id": task_id,
        "level": 2,
        "golden_action": [{"tool": "A", "args": {"q": "x"}}],
        "tool_calls": [{"tool_name": tool_name, "arguments": {"q": "x"}, "success": True}],
    }



def _l6_no_call_task(task_id):
    return {
        "task_id": task_id,
        "level": 6,
        "final_response": "",
        "golden_action": [
            {"tool": "A", "args": {}},
            {"action": "context_used"},
        ],
        "golden_fields": [{"tool": "ToolA", "fields": ["item.title"]}],
        "conversation_tracking": _l6_schema(
            fields=["item.title"],
            result={"item": {"title": "seeded title"}},
        )["conversation_tracking"],
        "tool_calls": [],
    }



def _bench_map(tasks):
    mapped = {}
    for task in tasks:
        bench_task = {
            "task_id": task["task_id"],
            "golden_action": task["golden_action"],
        }
        for key in ("golden_fields", "conversation_tracking", "minimum_calls"):
            if key in task:
                bench_task[key] = task[key]
        mapped[task["task_id"]] = bench_task
    return mapped



def _task_id_producer(scored_ids, value=1.0):
    def _score(ctx):
        return value if ctx.task_schema.get("task_id") in scored_ids else None

    return _score



def _toy_task(task_id):
    return {
        "task_id": task_id,
        "level": 1,
        "golden_action": [],
        "tool_calls": [],
    }



def _with_level_specs(level, specs, callback):
    original = score_run.LEVEL_SPECS[level]
    score_run.LEVEL_SPECS[level] = specs
    try:
        return callback()
    finally:
        score_run.LEVEL_SPECS[level] = original


__all__ = [name for name in globals() if not name.startswith("__")]
