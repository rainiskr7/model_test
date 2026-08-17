"""tool_call_parser 단독 실행 테스트.

패키지 import 없이 파일 경로에서 직접 로드한다.
"""

import ast
import contextlib
import importlib.util
import io
import json
import os
import signal
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


PARSER_PATH = (
    Path(__file__).resolve().parents[1]
    / "gpustack_custom"
    / "tool_call_parser.py"
)
CUSTOM_DIR = PARSER_PATH.parent
ADAPTER_PATH = CUSTOM_DIR / "openai_compat_adapter.py"
RUNNER_PATH = CUSTOM_DIR / "run_gpustack_benchmark_with_logging.py"


def _load_parser():
    spec = importlib.util.spec_from_file_location("tool_call_parser_under_test", PARSER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


parser = _load_parser()


def _load_adapter_parse_class():
    """선택 의존성을 import하지 않고 adapter의 실제 text parser method를 로드한다."""
    parsed = ast.parse(ADAPTER_PATH.read_text(encoding="utf-8"), filename=str(ADAPTER_PATH))
    adapter_class = next(
        node
        for node in parsed.body
        if isinstance(node, ast.ClassDef) and node.name == "OpenAICompatAdapter"
    )
    method = next(
        node
        for node in adapter_class.body
        if isinstance(node, ast.FunctionDef) and node.name == "_parse_tool_calls_from_text"
    )
    test_class = ast.ClassDef(
        name="AdapterTextParser",
        bases=[],
        keywords=[],
        body=[method],
        decorator_list=[],
    )
    module = ast.fix_missing_locations(ast.Module(body=[test_class], type_ignores=[]))
    namespace = {
        "Any": Any,
        "Dict": Dict,
        "contains_tool_call_candidate": parser.contains_tool_call_candidate,
        "extract_tool_calls": parser.extract_tool_calls,
        "sys": sys,
    }
    exec(compile(module, str(ADAPTER_PATH), "exec"), namespace)
    return namespace["AdapterTextParser"]


def _load_save_detailed_results():
    """벤치 선택 의존성 없이 실제 artifact 저장 함수를 로드한다."""
    parsed = ast.parse(RUNNER_PATH.read_text(encoding="utf-8"), filename=str(RUNNER_PATH))
    function = next(
        node
        for node in parsed.body
        if isinstance(node, ast.FunctionDef) and node.name == "save_detailed_results"
    )
    namespace = {
        "Any": Any,
        "Dict": Dict,
        "List": List,
        "Optional": Optional,
        "Path": Path,
        "datetime": datetime,
        "json": json,
        "os": os,
        "simplify_result": lambda result: dict(result),
        "build_observability_metadata": lambda _results: {
            "tasks_with_length_finish_reason": 0
        },
    }
    exec(
        compile(ast.Module(body=[function], type_ignores=[]), str(RUNNER_PATH), "exec"),
        namespace,
    )
    return namespace["save_detailed_results"]


AdapterTextParser = _load_adapter_parse_class()
save_detailed_results = _load_save_detailed_results()


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


def test_colon_text_form_multiple_calls():
    calls = parser.extract_tool_calls(
        'call:Directions_naver:{"start": "126.97070,37.55360", '
        '"goal": "126.45123,37.46349", '
        '"waypoints": "126.97688,37.57594|126.92490,37.52190", '
        '"option": "traavoidtoll"}\n'
        'call:ItemSearch_aladin:{"query": "히가시노 게이고", "sort": "SalesPoint"}'
    )
    _assert(len(calls) == 2, f"expected 2 form-B calls, got {len(calls)}")
    _assert(
        [call["function"]["name"] for call in calls]
        == ["Directions_naver", "ItemSearch_aladin"],
        "form-B names mismatch",
    )
    _assert(_arguments(calls[0])["option"] == "traavoidtoll", "form-B args mismatch")


def test_braceless_separator_text_form_multiple_calls():
    calls = parser.extract_tool_calls(
        'call:ItemSearch_aladin{"query": "히가시노 게이고", "sort": "SalesPoint"}\n'
        'call:VideoSearch_daum{"query": "손흥민 해트트릭"}'
    )
    _assert(len(calls) == 2, f"expected 2 form-C calls, got {len(calls)}")
    _assert(
        [call["function"]["name"] for call in calls]
        == ["ItemSearch_aladin", "VideoSearch_daum"],
        "form-C names mismatch",
    )
    _assert(_arguments(calls[1]) == {"query": "손흥민 해트트릭"}, "form-C args mismatch")


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


def _assert_unparsed_candidate(content):
    adapter = AdapterTextParser()
    adapter.unparsed_tool_call_candidates = 0
    canonical = {"message": {"content": content}, "finish_reason": "length"}
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        returned = adapter._parse_tool_calls_from_text(canonical)
    _assert(returned is canonical, "adapter must return the canonical response")
    _assert("tool_calls" not in canonical["message"], "truncated call must not be fabricated")
    _assert(
        adapter.unparsed_tool_call_candidates == 1,
        "unparsed candidate counter did not increment",
    )
    _assert(
        "[adapter] 파싱되지 않은 tool call 후보:" in stderr.getvalue(),
        f"missing unparsed-candidate warning: {stderr.getvalue()!r}",
    )


def test_truncated_json_form_is_unparsed_candidate():
    _assert_unparsed_candidate(
        '{"tool_call": {"name": "Directions_naver", "arguments": {"start": "126.97"}'
    )


def test_truncated_text_forms_are_unparsed_candidates():
    _assert_unparsed_candidate('call:Directions_naver:{"start": "126.97", "goal": ')
    _assert_unparsed_candidate('call:ItemSearch_aladin{"query": "히가시노 게이고"')


def test_ordinary_prose_is_not_unparsed_candidate():
    adapter = AdapterTextParser()
    adapter.unparsed_tool_call_candidates = 0
    canonical = {
        "message": {"content": "요청하신 내용을 확인했습니다. 일반 답변을 드립니다."},
        "finish_reason": "stop",
    }
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        adapter._parse_tool_calls_from_text(canonical)
    _assert(adapter.unparsed_tool_call_candidates == 0, "prose triggered candidate counter")
    _assert(stderr.getvalue() == "", f"prose triggered warning: {stderr.getvalue()!r}")


def test_unparsed_candidate_counter_is_persisted_in_level_metadata():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = save_detailed_results(
            [{}],
            "test/model",
            "L1",
            tmpdir,
            "test_timestamp",
            unparsed_tool_call_candidates=3,
            request_timeout=60,
            task_timeout=120,
            max_tokens=1024,
            max_retries=2,
            openai_sdk_version="test",
            sdk_max_retries=0,
        )
        artifact = json.loads(Path(path).read_text(encoding="utf-8"))
    _assert(
        artifact["metadata"]["unparsed_tool_call_candidates"] == 3,
        "unparsed candidate counter missing from level metadata",
    )


def test_unparsed_candidate_counter_is_wired_from_adapter_to_artifact():
    adapter_tree = ast.parse(
        ADAPTER_PATH.read_text(encoding="utf-8"), filename=str(ADAPTER_PATH)
    )
    adapter_class = next(
        node
        for node in adapter_tree.body
        if isinstance(node, ast.ClassDef) and node.name == "OpenAICompatAdapter"
    )
    initializer = next(
        node
        for node in adapter_class.body
        if isinstance(node, ast.FunctionDef) and node.name == "__init__"
    )
    initialized = any(
        isinstance(target, ast.Attribute)
        and isinstance(target.value, ast.Name)
        and target.value.id == "self"
        and target.attr == "unparsed_tool_call_candidates"
        for node in ast.walk(initializer)
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
    )
    _assert(initialized, "adapter counter is not initialized")

    runner_tree = ast.parse(
        RUNNER_PATH.read_text(encoding="utf-8"), filename=str(RUNNER_PATH)
    )
    run_function = next(
        node
        for node in runner_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "run_benchmark_on_dataset"
    )
    wired = False
    for call in (node for node in ast.walk(run_function) if isinstance(node, ast.Call)):
        if not isinstance(call.func, ast.Name) or call.func.id != "save_detailed_results":
            continue
        keyword = next(
            (item for item in call.keywords if item.arg == "unparsed_tool_call_candidates"),
            None,
        )
        value = keyword.value if keyword is not None else None
        wired = (
            isinstance(value, ast.Attribute)
            and value.attr == "unparsed_tool_call_candidates"
            and isinstance(value.value, ast.Name)
            and value.value.id == "adapter"
        )
    _assert(wired, "adapter counter is not passed to level artifact persistence")


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
    test_colon_text_form_multiple_calls,
    test_braceless_separator_text_form_multiple_calls,
    test_markdown_json_fence,
    test_surrounding_prose,
    test_plain_text_without_tool_call,
    test_truncated_json_form_is_unparsed_candidate,
    test_truncated_text_forms_are_unparsed_candidates,
    test_ordinary_prose_is_not_unparsed_candidate,
    test_unparsed_candidate_counter_is_persisted_in_level_metadata,
    test_unparsed_candidate_counter_is_wired_from_adapter_to_artifact,
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
