"""tool_call_parser 단독 실행 테스트.

패키지 import 없이 파일 경로에서 직접 로드한다.
"""

import contextlib
import importlib.util
import io
import json
import signal
import sys
from pathlib import Path


PARSER_PATH = (
    Path(__file__).resolve().parents[1]
    / "gpustack_custom"
    / "tool_call_parser.py"
)


def _load_parser():
    spec = importlib.util.spec_from_file_location("tool_call_parser_under_test", PARSER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


parser = _load_parser()


def _arguments(call):
    return json.loads(call["function"]["arguments"])


def _assert(condition, message):
    if not condition:
        raise AssertionError(message)


def test_nested_arguments_regression():
    payload = (
        '{"tool_call": {"name": "Directions_naver", "arguments": {'
        '"start": "127.111221,37.395441", '
        '"goal": "127.071707,37.514085", '
        '"option": "trafast"}}}'
    )
    calls = parser.extract_tool_calls(payload)
    _assert(len(calls) == 1, f"expected 1 call, got {len(calls)}")
    _assert(calls[0]["function"]["name"] == "Directions_naver", "name mismatch")
    args = _arguments(calls[0])
    _assert(args["start"] == "127.111221,37.395441", "start argument lost")
    _assert(args["goal"] == "127.071707,37.514085", "goal argument lost")
    _assert(args["option"] == "trafast", "option argument lost")


def test_two_level_nested_arguments():
    calls = parser.extract_tool_calls(
        '{"tool_call": {"name": "Deep", "arguments": {"a": {"b": {"c": 1}}}}}'
    )
    _assert(len(calls) == 1, f"expected 1 call, got {len(calls)}")
    _assert(_arguments(calls[0]) == {"a": {"b": {"c": 1}}}, "nested args mismatch")


def test_multiple_tool_calls():
    calls = parser.extract_tool_calls(
        '{"tool_call": {"name": "First", "arguments": {"x": 1}}}\n'
        '{"tool_call": {"name": "Second", "arguments": {"y": 2}}}'
    )
    _assert(len(calls) == 2, f"expected 2 calls, got {len(calls)}")
    _assert([c["function"]["name"] for c in calls] == ["First", "Second"], "order mismatch")


def test_markdown_json_fence():
    calls = parser.extract_tool_calls(
        '```json\n{"tool_call": {"name": "Fenced", "arguments": {"ok": true}}}\n```'
    )
    _assert(len(calls) == 1, f"expected 1 call, got {len(calls)}")
    _assert(_arguments(calls[0]) == {"ok": True}, "fenced args mismatch")


def test_surrounding_prose():
    calls = parser.extract_tool_calls(
        '먼저 경로를 찾겠습니다.\n'
        '{"tool_call": {"name": "Directions_naver", "arguments": {"option": "trafast"}}}'
        "\n이후 결과를 확인하겠습니다."
    )
    _assert(len(calls) == 1, f"expected 1 call, got {len(calls)}")
    _assert(calls[0]["function"]["name"] == "Directions_naver", "prose name mismatch")


def test_plain_text_without_tool_call():
    calls = parser.extract_tool_calls("도구 호출 없이 일반 답변입니다.")
    _assert(calls == [], f"expected empty list, got {calls}")


def test_broken_json_warns_without_raising():
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        calls = parser.extract_tool_calls('{"tool_call": {"name": ')
    _assert(calls == [], f"expected empty list, got {calls}")
    _assert(stderr.getvalue().startswith("[adapter] "), "missing adapter warning")


def test_missing_name_is_skipped():
    calls = parser.extract_tool_calls('{"tool_call": {"arguments": {"x": 1}}}')
    _assert(calls == [], f"expected empty list, got {calls}")


def test_korean_arguments_preserved():
    calls = parser.extract_tool_calls(
        '{"tool_call": {"name": "Search", "arguments": {"query": "서울 맛집"}}}'
    )
    _assert(len(calls) == 1, f"expected 1 call, got {len(calls)}")
    serialized = calls[0]["function"]["arguments"]
    _assert("서울 맛집" in serialized, f"korean text escaped or lost: {serialized}")
    _assert(_arguments(calls[0]) == {"query": "서울 맛집"}, "korean args mismatch")


def test_case_a_quoted_marker_after_valid_call_does_not_hang():
    def _timeout(_signum, _frame):
        raise TimeoutError("case A parser timeout")

    previous = signal.signal(signal.SIGALRM, _timeout)
    signal.alarm(5)
    try:
        calls = parser.extract_tool_calls(
            '{"tool_call": {"name": "A", "arguments": {}}}\n'
            '위 "tool_call" 형식입니다.'
        )
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)

    _assert(len(calls) == 1, f"expected 1 call, got {len(calls)}")
    _assert(calls[0]["function"]["name"] == "A", "case A name mismatch")


def test_case_b_valid_call_after_other_json():
    calls = parser.extract_tool_calls(
        '{"status": "ok"}\n'
        '{"tool_call": {"name": "B", "arguments": {"value": 1}}}'
    )
    _assert(len(calls) == 1, f"expected 1 call, got {len(calls)}")
    _assert(calls[0]["function"]["name"] == "B", "case B name mismatch")


def test_case_c_brace_inside_string_before_marker():
    calls = parser.extract_tool_calls(
        '{"note": "brace { here", "tool_call": {"name": "C", "arguments": {}}}'
    )
    _assert(len(calls) == 1, f"expected 1 call, got {len(calls)}")
    _assert(calls[0]["function"]["name"] == "C", "case C name mismatch")


def test_case_d_template_echo_is_rejected_with_warning():
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        calls = parser.extract_tool_calls(
            '형식: {"tool_call": {"name": "<t>", "arguments": {...}}}'
        )
    _assert(calls == [], f"expected empty list, got {calls}")
    _assert(stderr.getvalue().startswith("[adapter] "), "case D missing adapter warning")


def test_case_e_string_arguments_are_preserved():
    calls = parser.extract_tool_calls(
        '{"tool_call": {"name": "E", "arguments": "raw"}}'
    )
    _assert(len(calls) == 1, f"expected 1 call, got {len(calls)}")
    _assert(calls[0]["function"]["name"] == "E", "case E name mismatch")
    _assert(calls[0]["function"]["arguments"] == "raw", "case E arguments mismatch")


def test_case_f_nested_wrapper_extracts_call():
    calls = parser.extract_tool_calls(
        '{"response": {"tool_call": {"name": "F", "arguments": {"ok": true}}}}'
    )
    _assert(len(calls) == 1, f"expected 1 call, got {len(calls)}")
    _assert(calls[0]["function"]["name"] == "F", "case F name mismatch")
    _assert(_arguments(calls[0]) == {"ok": True}, "case F args mismatch")


TESTS = [
    test_nested_arguments_regression,
    test_two_level_nested_arguments,
    test_multiple_tool_calls,
    test_markdown_json_fence,
    test_surrounding_prose,
    test_plain_text_without_tool_call,
    test_broken_json_warns_without_raising,
    test_missing_name_is_skipped,
    test_korean_arguments_preserved,
    test_case_a_quoted_marker_after_valid_call_does_not_hang,
    test_case_b_valid_call_after_other_json,
    test_case_c_brace_inside_string_before_marker,
    test_case_d_template_echo_is_rejected_with_warning,
    test_case_e_string_arguments_are_preserved,
    test_case_f_nested_wrapper_extracts_call,
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
