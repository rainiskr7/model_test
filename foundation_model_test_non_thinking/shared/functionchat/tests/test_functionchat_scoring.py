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
        # 채점기는 raw_response/error 로 "API 실패" 와 "모델이 툴을 안 부름" 을 가른다.
        # 기본값은 **정상 응답**이어야 한다 — 없으면 모든 픽스처가 생성 실패로 분류된다.
        "raw_response": {"message": {}},
        "error": None,
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



def test_dialog_coverage_mismatch_is_caught():
    """dialog 은 턴 단위로 평가하는데 커버리지를 시나리오 수로 적으면 안 된다.
    2026-08-23 에 45(시나리오)로 적혀 판정 필요 항목이 130 대신 45 로 집계됐고
    total_items 가 551(실제 636)로 발행됐다."""
    # 무결성 검사가 요구하는 필드를 코드에서 그대로 가져와 채운다 — 목록이 바뀌면
    # 이 테스트가 조용히 통과하지 않고 같이 따라간다.
    meta = {field: "x" for field in score.INTEGRITY_FIELDS}
    raw = {
        name: {"results": [], "metadata": dict(meta)}
        for name in ("singlecall", "call_decision", "dialog")
    }
    coverage = {
        "datasets": {},
        "not_measured": {
            "call_decision": {},
            "dialog": {"multi_turn": 45},   # 시나리오 수 — 틀렸다
        },
    }
    try:
        score.build_summary(raw, coverage, "functionchat")
    except ValueError as exc:
        _assert("Dialog not-measured" in str(exc), f"wrong error: {exc}")
        return
    raise AssertionError("dialog 커버리지 불일치를 잡지 못했다")



def test_content_in_model_output_does_not_affect_exact_match():
    """판정 계층을 위해 model_output 에 content 를 넣었다. exact-match 는 tool_calls 만
    보므로 결과가 달라지면 안 된다."""
    item = {
        "ground_truth": {
            "role": "assistant",
            "tool_calls": [{"function": {"name": "f", "arguments": '{"a": 1}'}}],
        },
        "acceptable_arguments": None,
    }
    out_without = {"tool_calls": [{"function": {"name": "f", "arguments": '{"a": 1}'}}]}
    out_with = dict(out_without, content="네, 조회해 드리겠습니다.")
    _assert(
        exact.exact_match(dict(item), out_without) == exact.exact_match(dict(item), out_with),
        "content 유무가 exact-match 결과를 바꿨다",
    )


def test_not_measured_items_still_carry_a_response():
    """비-call 항목도 호출·저장해야 판정 계층이 쓸 수 있다.
    2026-08-23 이전에는 130건 전부 model_output=null 이었다."""
    import inspect
    src = inspect.getsource(runner.run_item)
    _assert("evaluation_status" in src, "run_item 이 채점 대상 여부를 인자로 받아야 한다")
    _assert(
        not hasattr(runner, "not_measured_item"),
        "생성을 건너뛰던 not_measured_item 이 남아 있으면 안 된다",
    )



def _load_judge_mod():
    import importlib.util, sys as _s
    base = Path(__file__).resolve().parents[1] / "judge"
    _s.path.insert(0, str(base))
    spec = importlib.util.spec_from_file_location("run_judge_under_test", base / "run_judge.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_lost_vote_cannot_produce_a_single_vote_verdict():
    """2회 중 1회가 전송 실패하면 남은 1표로 판정이 확정되던 구멍.
    전송 실패가 조용히 반복 수를 깎고 그 사실이 어디에도 남지 않았다."""
    m = _load_judge_mod()
    _assert(m.majority([None, "fail"]) == "fail", "majority 자체는 유효표 기준이 맞다")
    integ = m.vote_integrity([None, "fail"], 2)
    _assert(integ["lost"] == 1 and integ["single_vote"], f"유실 기록이 없다: {integ}")


def test_vote_integrity_records_full_votes():
    m = _load_judge_mod()
    integ = m.vote_integrity(["pass", "pass"], 2)
    _assert(integ["lost"] == 0 and not integ["single_vote"], f"정상인데 유실로 잡혔다: {integ}")


def test_non_retryable_http_errors_are_not_retried():
    """400 을 3회 재시도해도 성공할 수 없다. 429/408 만 재시도한다."""
    import inspect
    src = inspect.getsource(exact.__class__) if False else None
    import importlib.util, sys as _s
    base = Path(__file__).resolve().parents[1] / "judge"
    _s.path.insert(0, str(base))
    spec = importlib.util.spec_from_file_location("judge_pilot_under_test", base / "judge_pilot.py")
    jp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(jp)
    body = inspect.getsource(jp.call_judge)
    _assert("408, 429" in body, "재시도 예외 목록(408/429)이 없다")
    _assert("Retry-After" in body, "429 의 Retry-After 를 존중하지 않는다")
    _assert("exc.read()" in body, "HTTP 에러 본문을 읽지 않아 실제 사유가 사라진다")



def test_api_failure_is_not_scored_as_a_model_failure():
    """타임아웃/401/500 이 모델 오답 하나로 둔갑하던 경로. 채점에서 제외하고 별도로 센다."""
    gt = {"role": "assistant", "tool_calls": [{"function": {"name": "f", "arguments": "{}"}}]}
    ok = {"type_of_output": "call", "ground_truth": gt, "acceptable_arguments": None,
          "raw_response": {"message": {}}, "error": None,
          "model_output": {"tool_calls": [{"function": {"name": "f", "arguments": "{}"}}]}}
    api_fail = {"type_of_output": "call", "ground_truth": gt, "acceptable_arguments": None,
                "raw_response": None, "error": "APITimeoutError: ...",
                "model_output": {"tool_calls": [], "content": None}}
    r = score.score_items([ok, api_fail])
    _assert(r["measured"] == 1, f"API 실패가 measured 에 들어갔다: {r}")
    _assert(r["passed"] == 1 and r["failed"] == 0, f"점수가 오염됐다: {r}")
    _assert(r["generation_errors"] == 1, f"생성 실패가 기록되지 않았다: {r}")


def test_genuine_no_tool_call_is_still_a_model_failure():
    """응답은 정상인데 툴을 안 부른 것은 진짜 모델 실패다. API 실패와 구분해야 한다."""
    gt = {"role": "assistant", "tool_calls": [{"function": {"name": "f", "arguments": "{}"}}]}
    no_call = {"type_of_output": "call", "ground_truth": gt, "acceptable_arguments": None,
               "raw_response": {"message": {"content": "죄송합니다"}}, "error": None,
               "model_output": {"tool_calls": [], "content": "죄송합니다"}}
    r = score.score_items([no_call])
    _assert(r["measured"] == 1 and r["failed"] == 1, f"진짜 실패가 제외됐다: {r}")
    _assert(r["generation_errors"] == 0, f"생성 실패로 오분류됐다: {r}")


def test_generation_errors_block_publish():
    s = _fc_summary()
    s["by_dataset"]["singlecall"]["generation_errors"] = 3
    failures, _ = score.validate_summary(s)
    _assert(any("생성 실패" in f for f in failures), f"게이트가 막지 않았다: {failures}")


def test_judge_rejects_non_enum_verdict():
    """{"verdict": "error"} 같은 값이 judged 로 확정되면서 pass/fail 어디에도
    안 세어져 조용히 사라지던 경로."""
    import importlib.util, sys as _s, inspect
    base = Path(__file__).resolve().parents[1] / "judge"
    _s.path.insert(0, str(base))
    spec = importlib.util.spec_from_file_location("jp_verdict_test", base / "judge_pilot.py")
    jp = importlib.util.module_from_spec(spec); spec.loader.exec_module(jp)
    src = inspect.getsource(jp.call_judge)
    _assert('("pass", "fail")' in src, "verdict 값을 검증하지 않는다")


judge_pilot = _load(
    "functionchat_judge_pilot_under_test",
    EXACT_PATH.parent.parent / "judge" / "judge_pilot.py",
)


def test_judge_records_what_the_endpoint_actually_served():
    """`openai/gpt-4.1-mini` 는 alias 다 — 문자열이 그대로여도 리비전은 바뀐다."""

    judge_pilot.SERVED_IDENTITY["model"].clear()
    judge_pilot.SERVED_IDENTITY["provider"].clear()
    judge_pilot.SERVED_IDENTITY["system_fingerprint"].clear()
    _assert(judge_pilot.served_identity_snapshot() == {}, "초기 상태가 비어 있어야 한다")

    judge_pilot.record_served_identity(
        {"model": "openai/gpt-4.1-mini-2025-04-14", "provider": "OpenAI"}
    )
    judge_pilot.record_served_identity({"model": "openai/gpt-4.1-mini-2025-04-14"})
    snapshot = judge_pilot.served_identity_snapshot()
    _assert(snapshot["model"] == ["openai/gpt-4.1-mini-2025-04-14"], snapshot)
    _assert(snapshot["provider"] == ["OpenAI"], snapshot)

    # 런 도중 서빙이 바뀌면 둘 다 남는다 — 하나로 덮으면 그 사실이 사라진다.
    judge_pilot.record_served_identity({"model": "openai/gpt-4.1-mini-2026-01-01"})
    _assert(len(judge_pilot.served_identity_snapshot()["model"]) == 2, "변경 이력이 남아야 한다")


def test_rubric_digest_changes_when_the_rubric_text_changes():
    """"unmodified" 라는 문장은 주장일 뿐이고, 본문이 바뀌어도 그대로다."""

    first = judge_pilot.rubric_digest({"singlecall": "본문", "dialog": "다른 본문"})
    same = judge_pilot.rubric_digest({"dialog": "다른 본문", "singlecall": "본문"})
    changed = judge_pilot.rubric_digest({"singlecall": "본문 수정됨", "dialog": "다른 본문"})
    _assert(first == same, "키 순서가 해시를 바꾸면 안 된다")
    _assert(first["singlecall"] != changed["singlecall"], "본문이 바뀌면 해시가 바뀌어야 한다")
    _assert(first["dialog"] == changed["dialog"], "안 바뀐 루브릭은 그대로여야 한다")


def test_judge_endpoint_is_recorded_not_hardcoded_at_the_call_site():
    source = (EXACT_PATH.parent.parent / "judge" / "judge_pilot.py").read_text(encoding="utf-8")
    call_site = source.split("def call_judge")[1]
    _assert(
        "https://openrouter.ai" not in call_site,
        "호출부에 URL 을 박으면 산출물에 어디로 보냈는지 남지 않는다",
    )
    _assert("JUDGE_ENDPOINT" in call_site, "상수를 써야 judge 블록에 기록할 수 있다")


repro = _load(
    "functionchat_repro_under_test", EXACT_PATH.parent / "repro.py"
)


def _run(session, model, version, items):
    return {"session": session, "model": model, "scoring_version": version,
            "publishable": True, "items": items}


def test_repro_compares_item_sets_not_counts():
    """실측: qwen 5런이 전부 553 인데 통과 항목은 10개가 뒤집혔다."""

    a = _run("r1", "m", "v1", {"i1": True, "i2": True, "i3": False})
    b = _run("r2", "m", "v1", {"i1": True, "i2": False, "i3": True})
    [report] = repro.reproducibility_report([a, b])
    _assert(report["status"] == "DIVERGED", report)
    _assert(report["passed_counts"] == [2, 2], report)
    _assert(report["count_spread"] == 0, "건수만 보면 완벽 재현으로 보인다")
    _assert(report["unstable_items"] == ["i2", "i3"], report)
    _assert(report["stable_passed"] == 1, report)


def test_repro_identical_when_the_same_items_pass():
    same = {"i1": True, "i2": False}
    [report] = repro.reproducibility_report([_run("r1", "m", "v1", same),
                                             _run("r2", "m", "v1", dict(same))])
    _assert(report["status"] == "IDENTICAL", report)
    _assert(report["unstable_items"] == [], report)


def test_repro_never_mixes_scoring_versions():
    """v1 은 600문항, v2 는 670문항이다 — 같은 이름의 다른 측정이다."""

    reports = repro.reproducibility_report([
        _run("r1", "m", "functionchat_exact_v1", {"i1": True}),
        _run("r2", "m", "functionchat_exact_v2", {"i1": True}),
    ])
    _assert(len(reports) == 2, reports)
    _assert(all(r["status"] == "UNVERIFIED" for r in reports), reports)


def test_repro_separates_models():
    """후보를 코호트 키에서 빼면 서로 다른 모델이 서로의 반복 실행이 된다."""

    reports = repro.reproducibility_report([
        _run("r1", "a", "v1", {"i1": True}),
        _run("r2", "b", "v1", {"i1": False}),
    ])
    _assert({r["model"] for r in reports} == {"a", "b"}, reports)
    _assert(all(r["status"] == "UNVERIFIED" for r in reports), reports)


def test_repro_ignores_unmeasured_items_rather_than_failing_them():
    """하네스 장애를 실패로 세면 모델 점수로 둔갑한다."""

    import json as _json
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp) / "results" / "m" / "s" / "language" / "functionchat"
        run_dir.mkdir(parents=True)
        (run_dir / "summary.json").write_text(
            _json.dumps({"model": "m", "scoring_version": "v1",
                         "publish_status": {"publishable": True}}), encoding="utf-8")
        (run_dir / "singlecall.json").write_text(_json.dumps({"results": [
            {"item_id": "ok", "evaluation_status": "measured", "type_of_output": "call",
             "raw_response": "{}", "error": None,
             "ground_truth": None, "model_output": None},
            # 채점 대상이 아닌 유형 — 점수에 들어가지 않는다
            {"item_id": "other_type", "evaluation_status": "not_measured",
             "type_of_output": "relevance", "raw_response": "{}", "error": None},
            # **API 실패.** evaluation_status 는 여전히 measured 다. 이것을 오답으로
            # 세면 타임아웃 하나가 모델 오답 하나로 둔갑한다.
            {"item_id": "api_failed", "evaluation_status": "measured",
             "type_of_output": "call", "raw_response": None, "error": "timeout",
             "ground_truth": None, "model_output": None},
        ]}), encoding="utf-8")
        loaded = repro.load_run(run_dir)
    _assert(loaded["session"] == "s", loaded)
    _assert(set(loaded["items"]) == {"ok"}, loaded["items"])


def test_results_path_reuses_the_existing_directory_spelling():
    """리눅스에서는 대소문자가 다르면 한 런의 산출물이 두 디렉토리로 갈린다."""

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        (base / "results" / "Google_Gemma_4_26B_A4B_it").mkdir(parents=True)
        resolved = score.results_model_dir_name(base, "google/gemma-4-26b-a4b-it")
        _assert(resolved == "Google_Gemma_4_26B_A4B_it", resolved)
        # 새 모델은 정규화한 이름을 그대로 쓴다
        _assert(score.results_model_dir_name(base, "new/model:v1") == "new_model_v1", "신규")


def test_no_functionchat_entry_point_computes_the_path_by_substitution():
    for path in (RUNNER_PATH, SCORE_PATH):
        text = path.read_text(encoding="utf-8")
        if "safe_model_name" not in text:
            continue
        _assert(
            "results_model_dir_name" in text,
            f"{path.name} 이 문자열 치환으로 결과 경로를 만든다",
        )


def test_repro_and_scorer_agree_on_which_items_count():
    """규칙이 두 곳에 흩어지면 한쪽만 고쳐져 조용히 어긋난다."""

    items = [
        {"item_id": "a", "type_of_output": "call", "raw_response": "{}", "error": None,
         "ground_truth": None, "model_output": None},
        {"item_id": "b", "type_of_output": "relevance", "raw_response": "{}", "error": None},
        {"item_id": "c", "type_of_output": "call", "raw_response": None, "error": "timeout"},
    ]
    summary = score.score_items(items)
    _assert(summary["measured"] == 1, summary)
    _assert(summary["generation_errors"] == 1, summary)
    scorable = [i for i in items if score.scorable_status(i) == "scorable"]
    _assert([i["item_id"] for i in scorable] == ["a"], scorable)


def test_served_identity_resets_between_runs_and_merges_a_retry():
    """모듈 전역이라 리셋하지 않으면 앞선 실행이 다음 산출물로 샌다."""

    judge_pilot.record_served_identity({"model": "leftover-from-previous-run"})

    # 새 실행: 이전 기록 없이 시작한다
    judge_pilot.reset_served_identity(None)
    _assert(judge_pilot.served_identity_snapshot() == {}, "리셋이 비우지 않았다")

    # 재판정: 기존 judge.json 의 기록을 물려받아야 이미 확정된 항목의 출처가 남는다
    judge_pilot.reset_served_identity({"model": ["rev-a"], "provider": ["OpenAI"]})
    judge_pilot.record_served_identity({"model": "rev-b"})
    snapshot = judge_pilot.served_identity_snapshot()
    _assert(snapshot["model"] == ["rev-a", "rev-b"], snapshot)
    _assert(snapshot["provider"] == ["OpenAI"], snapshot)
    _assert("leftover-from-previous-run" not in snapshot["model"], snapshot)
    judge_pilot.reset_served_identity(None)


def test_repro_says_coverage_differed_instead_of_just_unverified():
    """항목 집합이 다르면 코호트가 갈린다 — 그 사유를 말하지 않으면
    "한 번만 돌렸다"로 읽혀 반복 실행이 있었다는 사실이 사라진다."""

    reports = repro.reproducibility_report([
        _run("r1", "m", "v1", {"i1": True, "i2": True}),
        _run("r2", "m", "v1", {"i1": True}),          # 항목 하나가 빠졌다
    ])
    _assert(len(reports) == 2, reports)
    _assert(all(r["status"] == "UNVERIFIED" for r in reports), reports)
    _assert(any("코호트가 2개로 갈렸다" in r["reason"] for r in reports), reports)


def test_repro_reports_which_dataset_file_could_not_be_read():
    """조용히 건너뛰면 읽기 실패가 재현성 결론으로 둔갑한다."""

    import json as _json
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp) / "results" / "m" / "s" / "language" / "functionchat"
        run_dir.mkdir(parents=True)
        (run_dir / "summary.json").write_text(
            _json.dumps({"model": "m", "scoring_version": "v1",
                         "publish_status": {"publishable": True}}), encoding="utf-8")
        (run_dir / "singlecall.json").write_text(_json.dumps({"results": [
            {"item_id": "ok", "evaluation_status": "measured", "type_of_output": "call",
             "raw_response": "{}", "error": None,
             "ground_truth": None, "model_output": None}]}), encoding="utf-8")
        (run_dir / "call_decision.json").write_text("{ 깨진", encoding="utf-8")
        loaded = repro.load_run(run_dir)
    _assert(loaded["unreadable_datasets"] == ["call_decision.json: JSONDecodeError"], loaded)

    [report] = repro.reproducibility_report([loaded])
    _assert("읽지 못한 산출물" in report["reason"], report["reason"])


def test_decoding_provenance_records_what_was_sent_not_what_was_asked():
    """요청값만 적으면 산출물이 거짓을 말한다.

    실제로 커밋된 diffusiongemma agent 런이 `max_tokens: 16384` 이라고 적고 있는데,
    그 런이 diffusion 엔드포인트에서 성공했다는 것 자체가 서빙 프로파일이 켜져
    있었다는 증거다 — 프로파일이 켜지면 4096 으로 잘린다.
    """

    import argparse
    import os

    runner_mod = _load(
        "functionchat_runner_under_test",
        EXACT_PATH.parent.parent / "runner" / "run_functionchat.py",
    )
    saved = {k: os.environ.get(k) for k in (
        "SERVING_UNSUPPORTED_SAMPLING_PARAMS", "SERVING_MAX_OUTPUT_TOKENS")}
    os.environ["SERVING_UNSUPPORTED_SAMPLING_PARAMS"] = "temperature,seed"
    os.environ["SERVING_MAX_OUTPUT_TOKENS"] = "4096"
    try:
        got = runner_mod._decoding_provenance(argparse.Namespace(max_tokens=16384))
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    _assert(got["available"], got)
    _assert(got["requested"]["max_tokens"] == 16384, got)
    _assert(got["effective"]["max_tokens"] == 4096, "실제로 보낸 값이 기록돼야 한다")
    _assert(got["effective"]["temperature"] is None, "제거된 파라미터는 None 이어야 한다")
    # 이 한 줄이 결론이다 — 이 런의 단일 숫자는 재현되지 않는다.
    _assert(got["deterministic_controls"] is False, got)


def test_decoding_provenance_says_controlled_when_nothing_is_removed():
    import argparse
    import os

    runner_mod = _load(
        "functionchat_runner_under_test2",
        EXACT_PATH.parent.parent / "runner" / "run_functionchat.py",
    )
    saved = os.environ.pop("SERVING_UNSUPPORTED_SAMPLING_PARAMS", None)
    try:
        got = runner_mod._decoding_provenance(argparse.Namespace(max_tokens=16384))
    finally:
        if saved is not None:
            os.environ["SERVING_UNSUPPORTED_SAMPLING_PARAMS"] = saved
    _assert(got["deterministic_controls"] is True, got)
    _assert(got["effective"]["temperature"] == 0.0, got)


def test_reproducibility_distinguishes_structural_drift_from_chance():
    """결정론 제어가 없으면 흔들림은 모델 결함이 아니다."""

    runs = [
        {"session": "s1", "model": "d", "scoring_version": "v1", "publishable": True,
         "items": {"a": True, "b": False}, "decoding_controlled": False,
         "removed_sampling_params": ["temperature"]},
        {"session": "s2", "model": "d", "scoring_version": "v1", "publishable": True,
         "items": {"a": False, "b": True}, "decoding_controlled": False,
         "removed_sampling_params": ["temperature"]},
    ]
    report = repro.reproducibility_report(runs)
    entry = next(e for e in report if e["model"] == "d")
    _assert(entry["status"] == "DIVERGED", entry)
    _assert(entry["decoding_controlled"] is False, entry)
    _assert("temperature" in entry["removed_sampling_params"], entry)


def test_reproducibility_does_not_claim_control_for_pre_provenance_runs():
    # 디코딩 기록이 없는 예전 산출물을 "제어됐다" 로 단정하면 안 된다.
    runs = [
        {"session": "s1", "model": "q", "scoring_version": "v1", "publishable": True,
         "items": {"a": True}, "decoding_controlled": None},
        {"session": "s2", "model": "q", "scoring_version": "v1", "publishable": True,
         "items": {"a": True}, "decoding_controlled": None},
    ]
    entry = next(e for e in repro.reproducibility_report(runs) if e["model"] == "q")
    _assert(entry["decoding_controlled"] is None, entry)


TESTS = [
    test_decoding_provenance_records_what_was_sent_not_what_was_asked,
    test_decoding_provenance_says_controlled_when_nothing_is_removed,
    test_reproducibility_distinguishes_structural_drift_from_chance,
    test_reproducibility_does_not_claim_control_for_pre_provenance_runs,
    test_served_identity_resets_between_runs_and_merges_a_retry,
    test_repro_says_coverage_differed_instead_of_just_unverified,
    test_repro_reports_which_dataset_file_could_not_be_read,
    test_repro_and_scorer_agree_on_which_items_count,
    test_results_path_reuses_the_existing_directory_spelling,
    test_no_functionchat_entry_point_computes_the_path_by_substitution,
    test_repro_compares_item_sets_not_counts,
    test_repro_identical_when_the_same_items_pass,
    test_repro_never_mixes_scoring_versions,
    test_repro_separates_models,
    test_repro_ignores_unmeasured_items_rather_than_failing_them,
    test_judge_records_what_the_endpoint_actually_served,
    test_rubric_digest_changes_when_the_rubric_text_changes,
    test_judge_endpoint_is_recorded_not_hardcoded_at_the_call_site,
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
    test_dialog_coverage_mismatch_is_caught,
    test_content_in_model_output_does_not_affect_exact_match,
    test_not_measured_items_still_carry_a_response,
    test_lost_vote_cannot_produce_a_single_vote_verdict,
    test_vote_integrity_records_full_votes,
    test_non_retryable_http_errors_are_not_retried,
    test_api_failure_is_not_scored_as_a_model_failure,
    test_genuine_no_tool_call_is_still_a_model_failure,
    test_generation_errors_block_publish,
    test_judge_rejects_non_enum_verdict,
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
