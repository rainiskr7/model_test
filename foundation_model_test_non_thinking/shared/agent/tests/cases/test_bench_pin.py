from _harness import *
import hashlib


task_source = _load_module("task_source")


def test_bench_pin_code_digests_are_hex_and_distinct():
    base = os.environ.get("MODEL_TEST_BASE")
    metrics_py = Path(base or "") / "data" / "Ko-AgentBench" / "bench" / "runner" / "metrics.py"
    runner_py = Path(base or "") / "data" / "Ko-AgentBench" / "bench" / "runner" / "run.py"
    if not base or not metrics_py.is_file() or not runner_py.is_file():
        print("SKIP test_bench_pin_code_digests_are_hex_and_distinct: vendored Ko-AgentBench not available")
        return

    pin = task_source.bench_pin(["L1"])
    for key in ("metrics_sha256", "runner_sha256"):
        value = pin.get(key)
        _assert(isinstance(value, str), f"{key} must be a string")
        _assert(len(value) == 64, f"{key} length")
        _assert(value == value.lower(), f"{key} lowercase")
        _assert(all(char in "0123456789abcdef" for char in value), f"{key} hex")
    _assert(pin["metrics_sha256"] != pin["runner_sha256"], "code digests should differ")

def test_bench_pin_code_digests_match_file_bytes():
    base = os.environ.get("MODEL_TEST_BASE")
    koa_dir = Path(base or "") / "data" / "Ko-AgentBench"
    metrics_py = koa_dir / "bench" / "runner" / "metrics.py"
    runner_py = koa_dir / "bench" / "runner" / "run.py"
    if not base or not metrics_py.is_file() or not runner_py.is_file():
        print("SKIP test_bench_pin_code_digests_match_file_bytes: vendored Ko-AgentBench not available")
        return

    pin = task_source.bench_pin(["L1"])
    _assert(
        pin["metrics_sha256"] == hashlib.sha256(metrics_py.read_bytes()).hexdigest(),
        "metrics.py digest",
    )
    _assert(
        pin["runner_sha256"] == hashlib.sha256(runner_py.read_bytes()).hexdigest(),
        "run.py digest",
    )

def test_bench_pin_tasks_sha256_shape_and_content_unchanged():
    base = os.environ.get("MODEL_TEST_BASE")
    tasks_dir = Path(base or "") / "data" / "Ko-AgentBench" / "bench" / "tasks"
    if not base or not (tasks_dir / "L1.json").is_file() or not (tasks_dir / "L6.json").is_file():
        print("SKIP test_bench_pin_tasks_sha256_shape_and_content_unchanged: vendored Ko-AgentBench not available")
        return

    levels = ["L1", "L6"]
    pin = task_source.bench_pin(levels)
    expected = {
        level: hashlib.sha256((tasks_dir / f"{level}.json").read_bytes()).hexdigest()
        for level in levels
    }
    _assert(pin["tasks_sha256"] == expected, "tasks_sha256 content")
    _assert(list(pin["tasks_sha256"]) == levels, "tasks_sha256 order")

def test_bench_pin_missing_code_file_records_none():
    original = task_source.ensure_bench_path

    class _MissingCodeBenchPath:
        def __truediv__(self, part):
            return original() / part

        def joinpath(self, *parts):
            if parts == ("bench", "runner", "metrics.py"):
                return Path("/tmp/agent-scoring-missing-metrics.py")
            return original().joinpath(*parts)

    task_source.ensure_bench_path = lambda: _MissingCodeBenchPath()
    try:
        pin = task_source.bench_pin(["L1"])
    finally:
        task_source.ensure_bench_path = original

    _assert(pin["metrics_sha256"] is None, "missing metrics.py should record None")
    _assert(isinstance(pin["runner_sha256"], str), "present runner.py should still hash")

def test_bench_pin_drift_key_comparison_ignores_unknown_and_reports_present_diff():
    old_without_new_keys = {"tasks_sha256": {"L1": "same"}}
    new_with_new_keys = {
        "tasks_sha256": {"L1": "same"},
        "metrics_sha256": "a" * 64,
        "runner_sha256": "b" * 64,
    }
    _assert(
        score_run._bench_pin_drift_keys(old_without_new_keys, new_with_new_keys) == [],
        "missing old digest keys are unknown, not drift",
    )
    _assert(
        score_run._bench_pin_drift_keys(new_with_new_keys, dict(new_with_new_keys)) == [],
        "equal pins should not drift",
    )
    changed = dict(new_with_new_keys)
    changed["metrics_sha256"] = "c" * 64
    _assert(
        score_run._bench_pin_drift_keys(new_with_new_keys, changed) == ["metrics_sha256"],
        "changed present digest key should be reported",
    )


TESTS = [
    test_bench_pin_code_digests_are_hex_and_distinct,
    test_bench_pin_code_digests_match_file_bytes,
    test_bench_pin_tasks_sha256_shape_and_content_unchanged,
    test_bench_pin_missing_code_file_records_none,
    test_bench_pin_drift_key_comparison_ignores_unknown_and_reports_present_diff,
]
