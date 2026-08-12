"""agent scoring 단독 실행 테스트.

패키지 import 없이 파일 경로에서 직접 로드한다.
"""

import importlib.util
import os
import sys
from pathlib import Path


SCORING_DIR = Path(__file__).resolve().parents[1] / "scoring"


def _load_module(name):
    path = SCORING_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"{name}_under_test", path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SCORING_DIR))
    try:
        spec.loader.exec_module(module)
    finally:
        try:
            sys.path.remove(str(SCORING_DIR))
        except ValueError:
            pass
    return module


extra_metrics = _load_module("extra_metrics")
level_spec = _load_module("level_spec")
score_run = _load_module("score_run")


class DummyContext:
    def __init__(self, golden_action, action_trace):
        self.task_schema = {"golden_action": golden_action}
        self.action_trace = action_trace


def _assert(condition, message):
    if not condition:
        raise AssertionError(message)


def _assert_close(actual, expected, message):
    if actual is None or abs(actual - expected) > 1e-9:
        raise AssertionError(f"{message}: expected {expected}, got {actual}")


def test_fsm_prefix_exact_match():
    ctx = DummyContext([{"tool": "A"}, {"tool": "B"}], [{"tool": "A"}, {"tool": "B"}])
    _assert_close(extra_metrics.fsm_prefix(ctx), 1.0, "exact match")


def test_fsm_prefix_with_extra_calls():
    ctx = DummyContext(
        [{"tool": "A"}, {"tool": "B"}],
        [{"tool": "A"}, {"tool": "B"}, {"tool": "C"}],
    )
    _assert_close(extra_metrics.fsm_prefix(ctx), 1.0, "prefix with extra calls")


def test_fsm_prefix_wrong_order():
    ctx = DummyContext([{"tool": "A"}, {"tool": "B"}], [{"tool": "B"}, {"tool": "A"}])
    _assert_close(extra_metrics.fsm_prefix(ctx), 0.0, "wrong order")


def test_fsm_prefix_empty_golden():
    ctx = DummyContext([], [{"tool": "A"}])
    _assert_close(extra_metrics.fsm_prefix(ctx), 0.0, "empty golden")


def test_fsm_prefix_empty_actual():
    ctx = DummyContext([{"tool": "A"}], [])
    _assert_close(extra_metrics.fsm_prefix(ctx), 0.0, "empty actual")


def test_mean_excludes_none():
    _assert_close(level_spec.mean_or_none([1.0, None, 0.0]), 0.5, "None excluded")


def test_mean_all_none():
    _assert(level_spec.mean_or_none([None, None]) is None, "all None should be None")


def test_in_score_false_excluded():
    entries = [
        {"score": 1.0, "in_score": True},
        {"score": 0.0, "in_score": False},
    ]
    _assert_close(level_spec.representative_score(entries), 1.0, "in_score false excluded")


def test_judge_missing_without_call():
    summary = score_run.score_level("L7", {"results": []})
    entry = summary["metrics"]["SR"]
    _assert(entry["status"] == "judge_missing", "judge status mismatch")
    _assert(entry["score"] is None, "judge score should be None")
    _assert(entry["in_score"] is False, "judge in_score should be false")


def test_missing_level_not_zero_filled():
    result = {
        "metadata": {"model": "x", "native_tool_calling": True, "success_rate": 100.0},
        "results": [],
    }
    summary = score_run.build_summary_from_loaded_for_test({"L7": result}, Path("/tmp/results/x/t/language/agent"))
    _assert("L1" in summary["levels_missing"], "missing L1 not recorded")
    _assert("L1" not in summary["by_level"], "missing L1 should not be zero-filled")
    _assert(summary["agent_score"] is None, "missing levels must not create score zero")


def test_arg_f1_det_or_skip():
    base = os.environ.get("MODEL_TEST_BASE")
    metrics_py = Path(base or "") / "data" / "Ko-AgentBench" / "bench" / "runner" / "metrics.py"
    if not base or not metrics_py.is_file():
        print("SKIP test_arg_f1_det_or_skip: vendored Ko-AgentBench not available")
        return

    context = _load_module("context")
    task = {
        "task_id": "x",
        "golden_action": [{"tool": "A", "args": {"q": "x"}}],
        "arg_schema": {},
        "tool_calls": [
            {"tool_name": "A", "arguments": {"q": "x"}, "success": True, "error": None}
        ],
    }
    ctx = context.build_eval_context(task)
    _assert_close(extra_metrics.arg_f1_det(ctx), 1.0, "arg_f1_det")


TESTS = [
    test_fsm_prefix_exact_match,
    test_fsm_prefix_with_extra_calls,
    test_fsm_prefix_wrong_order,
    test_fsm_prefix_empty_golden,
    test_fsm_prefix_empty_actual,
    test_mean_excludes_none,
    test_mean_all_none,
    test_in_score_false_excluded,
    test_judge_missing_without_call,
    test_missing_level_not_zero_filled,
    test_arg_f1_det_or_skip,
]


def main():
    failures = []
    for test in TESTS:
        try:
            test()
        except AssertionError as exc:
            failures.append(f"{test.__name__}: {exc}")
        except Exception as exc:
            failures.append(f"{test.__name__}: unexpected {type(exc).__name__}: {exc}")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}", file=sys.stderr)
        return 1

    print(f"OK {len(TESTS)} cases")
    return 0


if __name__ == "__main__":
    sys.exit(main())
