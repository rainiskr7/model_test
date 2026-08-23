"""FunctionChat exact-match port와 dataset expansion 회귀 테스트."""

import importlib.util
import json
import os
import sys
from pathlib import Path


FUNCTIONCHAT_DIR = Path(__file__).resolve().parents[1]
TREE_ROOT = Path(__file__).resolve().parents[3]
EXACT_PATH = FUNCTIONCHAT_DIR / "scoring" / "exact_match.py"
SCORE_PATH = FUNCTIONCHAT_DIR / "scoring" / "score_run.py"
RUNNER_PATH = FUNCTIONCHAT_DIR / "runner" / "run_functionchat.py"
BENCH_DIR = Path(
    os.environ.get("FUNCTIONCHAT_BENCH_DIR")
    or TREE_ROOT / "data" / "FunctionChat-Bench"
)
DATA_DIR = BENCH_DIR / "data"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


exact = _load("functionchat_exact_under_test", EXACT_PATH)
sys.path.insert(0, str(EXACT_PATH.parent))
try:
    score = _load("functionchat_score_under_test", SCORE_PATH)
finally:
    sys.path.remove(str(EXACT_PATH.parent))
runner = _load("functionchat_runner_under_test", RUNNER_PATH)


def _assert(condition, message):
    if not condition:
        raise AssertionError(message)


def _input(name="informWeather", arguments=None, acceptable=None, output_type="call"):
    return {
        "type_of_output": output_type,
        "ground_truth": {
            "name": name,
            "arguments": json.dumps(arguments or {}, ensure_ascii=False),
        },
        "acceptable_arguments": acceptable,
    }


def _output(name="informWeather", arguments=None):
    return {
        "tool_calls": [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "arguments": json.dumps(arguments or {}, ensure_ascii=False),
                },
            }
        ]
    }


def test_three_acceptable_argument_sentinels_are_empty():
    sentinels = (
        "Only ground truth is allowed.",
        "The date should be expressed as 'tomorrow'. A specific date should not be designated.",
        "Since the user did not mention a specific year, it will fail if the date was created including the year in the submission.",
    )
    for value in sentinels:
        _assert(
            exact.get_acceptable_arguments({"acceptable_arguments": value}) == {},
            f"sentinel must yield empty mapping: {value}",
        )


def test_hallucinated_argument_key_fails():
    inp = _input(arguments={"location": "서울"})
    out = _output(arguments={"location": "서울", "unit": "celsius"})
    _assert(not exact.exact_match(inp, out), "extra prediction key must fail")


def test_real_korean_string_ignores_spaces_and_case():
    # Singlecall serial 11과 15의 실제 정답 값으로 공백/대소문자 규칙을 고정한다.
    korean_inp = _input(arguments={"location": "제주도 서귀포시"})
    korean_out = _output(arguments={"location": "제주도서귀포시"})
    latin_inp = _input(name="getCurrentTimeForLocation", arguments={"location": "Honolulu"})
    latin_out = _output(
        name="getCurrentTimeForLocation", arguments={"location": "h O n O l U l U"}
    )
    _assert(exact.exact_match(korean_inp, korean_out), "spaces should be ignored")
    _assert(exact.exact_match(latin_inp, latin_out), "spaces/case should be ignored")


def test_acceptable_list_alternative_passes():
    inp = _input(
        arguments={"location": "제주도 서귀포시"},
        acceptable=json.dumps(
            {"location": ["서귀포시", "서귀포", "제주도 서귀포"]},
            ensure_ascii=False,
        ),
    )
    out = _output(arguments={"location": "서귀포"})
    _assert(exact.exact_match(inp, out), "acceptable list alternative should pass")


def test_wrong_function_name_fails_before_arguments():
    inp = _input(name="informWeather", arguments={"location": "서울"})
    out = _output(name="wrongFunction", arguments={"location": "서울"})
    original_compare = exact.compare_arguments

    def arguments_must_not_be_compared(*_args, **_kwargs):
        raise AssertionError("arguments were compared before the function name")

    exact.compare_arguments = arguments_must_not_be_compared
    try:
        _assert(not exact.exact_match(inp, out), "wrong function name must fail")
    finally:
        exact.compare_arguments = original_compare


def test_non_call_items_are_not_measured_not_failures():
    items = [
        {
            **_input(arguments={"location": "서울"}),
            "model_output": _output(arguments={"location": "서울"}),
        },
        {
            **_input(output_type="slot"),
            "model_output": None,
        },
        {
            **_input(output_type="relevance"),
            "model_output": _output(name="wrongFunction"),
        },
    ]
    result = score.score_items(items)
    _assert(result["measured"] == 1, f"expected one measured item: {result}")
    _assert(result["passed"] == 1 and result["failed"] == 0, str(result))
    _assert(result["not_measured"] == {"relevance": 1, "slot": 1}, str(result))


def test_singlecall_expansion_count_from_real_data():
    system_prompt = (DATA_DIR / "system_prompt.txt").read_text(encoding="utf-8").strip()
    items = runner.expand_singlecall(
        DATA_DIR / "FunctionChat-Singlecall.jsonl", system_prompt
    )
    _assert(len(items) == 500, f"expected 500 expanded items, got {len(items)}")
    _assert(
        len({item["item_id"] for item in items}) == 500,
        "expanded item ids must be unique",
    )



# --- 발행 게이트 ---
# 2026-08-19 에 gemma 런이 401 로 전 항목 실패했는데 파이프라인이 성공처럼 보였다.
# 인증 실패로 인한 전멸과 "모델이 정말 0점" 은 요약만 봐서는 구분되지 않으므로 막는다.


def _fc_summary(
    singlecall_measured=500, decision_measured=100, dialog_measured=70,
    passed=553, native=True,
):
    measured = singlecall_measured + decision_measured + dialog_measured
    return {
        "native_tool_calling": native,
        "overall": {"measured": measured, "passed": passed},
        "by_dataset": {
            "singlecall": {"measured": singlecall_measured},
            "call_decision": {"measured": decision_measured},
            "dialog": {"measured": dialog_measured},
        },
    }


def test_healthy_run_is_publishable():
    failures, warnings = score.validate_summary(_fc_summary())
    _assert(failures == [], f"healthy run should pass, got {failures}")
    _assert(warnings == [], f"healthy run should not warn, got {warnings}")


def test_total_failure_blocks_publish():
    failures, _ = score.validate_summary(_fc_summary(passed=0))
    _assert(any("전부 실패" in f for f in failures), f"expected total-failure gate, got {failures}")


def test_partial_run_blocks_publish():
    failures, _ = score.validate_summary(_fc_summary(singlecall_measured=250))
    _assert(any("부분 실행" in f for f in failures), f"expected partial-run gate, got {failures}")


def test_text_mode_warns_but_publishes():
    """텍스트 모드 점수는 유효하지만 native 런과 비교하면 안 된다 — 경고이지 실패가 아니다."""
    failures, warnings = score.validate_summary(_fc_summary(native=False))
    _assert(failures == [], f"text mode should still publish, got {failures}")
    _assert(any("native_tool_calling" in w for w in warnings), f"expected warning, got {warnings}")



def test_v1_artifacts_without_dialog_still_publishable():
    """2026-08-23 이전 산출물에는 dialog.json 이 없다. 재채점이 막히면 안 된다."""
    s = _fc_summary()
    del s["by_dataset"]["dialog"]
    s["overall"]["measured"] = 600
    failures, _ = score.validate_summary(s)
    _assert(failures == [], f"v1 artifact should still publish, got {failures}")


def test_dialog_present_but_short_blocks_publish():
    failures, _ = score.validate_summary(_fc_summary(dialog_measured=40))
    _assert(any("부분 실행" in f for f in failures), f"expected partial gate, got {failures}")


def test_dict_acceptable_arguments_is_returned_as_is():
    """Dialog 핀 데이터에 dict 형태가 3건 있다. 상류는 호출 전 json.dumps 로 우회한다."""
    got = exact.get_acceptable_arguments({"acceptable_arguments": {"city": ["서울", "Seoul"]}})
    _assert(got == {"city": ["서울", "Seoul"]}, f"dict should pass through, got {got}")


TESTS = [
    test_three_acceptable_argument_sentinels_are_empty,
    test_hallucinated_argument_key_fails,
    test_real_korean_string_ignores_spaces_and_case,
    test_acceptable_list_alternative_passes,
    test_wrong_function_name_fails_before_arguments,
    test_non_call_items_are_not_measured_not_failures,
    test_singlecall_expansion_count_from_real_data,
    test_healthy_run_is_publishable,
    test_total_failure_blocks_publish,
    test_partial_run_blocks_publish,
    test_text_mode_warns_but_publishes,
    test_v1_artifacts_without_dialog_still_publishable,
    test_dialog_present_but_short_blocks_publish,
    test_dict_acceptable_arguments_is_returned_as_is,
]


def main():
    failures = []
    for test in TESTS:
        try:
            test()
        except AssertionError as exc:
            failures.append(f"{test.__name__}: {exc}")
        except Exception as exc:
            failures.append(
                f"{test.__name__}: unexpected {type(exc).__name__}: {exc}"
            )
    if failures:
        for failure in failures:
            print(f"FAIL {failure}", file=sys.stderr)
        return 1
    print(f"OK {len(TESTS)} cases")
    return 0


if __name__ == "__main__":
    sys.exit(main())
