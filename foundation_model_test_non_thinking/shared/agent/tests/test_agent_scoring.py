"""agent scoring standalone test runner."""

import importlib.util
import sys
from pathlib import Path


CASES_DIR = Path(__file__).resolve().parent / "cases"
CASE_MODULES = [
    "test_metrics_basic",
    "test_l6",
    "test_l4",
    "test_l3",
    "test_l2",
    "test_level_specs",
    "test_data_health",
    "test_weighting",
    "test_passk",
    "test_bench_pin",
]


def _load_case_module(name):
    path = CASES_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"{name}_case", path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(CASES_DIR))
    try:
        spec.loader.exec_module(module)
    finally:
        try:
            sys.path.remove(str(CASES_DIR))
        except ValueError:
            pass
    return module


def _load_tests():
    tests = []
    for name in CASE_MODULES:
        tests.extend(_load_case_module(name).TESTS)
    return tests


TESTS = _load_tests()


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
