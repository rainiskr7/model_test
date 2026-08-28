"""tau2-bench 공식 split 선택과 upstream reward 변환 회귀 테스트."""

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


TAUBENCH_DIR = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


runner = load_module("taubench_runner_test", TAUBENCH_DIR / "runner" / "run_taubench.py")
scorer = load_module("taubench_scorer_test", TAUBENCH_DIR / "scoring" / "score_run.py")


def task(task_id, basis, nl_assertions=None):
    """nl_assertions 는 선언과 별개다 — 비어 있으면 상류가 판정 없이 1.0 을 준다."""
    criteria = {"reward_basis": basis}
    if nl_assertions:
        criteria["nl_assertions"] = list(nl_assertions)
    return {"id": task_id, "evaluation_criteria": criteria}


def simulation(task_id, reward):
    return {
        "task_id": task_id,
        "termination_reason": "agent_stop",
        "reward_info": {"reward": reward},
        "messages": [],
    }


def manifest(task_ids, split_name="test", task_count=None, not_measured_tasks=None):
    excluded = list(not_measured_tasks or [])
    return {
        "status": "completed",
        "model": "test/model",
        "source": {"commit": runner.SOURCE_COMMIT},
        "split": {
            "domain": "telecom",
            "name": split_name,
            "task_count": task_count if task_count is not None else len(task_ids),
            "runnable_task_count": len(task_ids),
            "task_ids": list(task_ids),
            "not_measured_task_count": len(excluded),
            "not_measured_tasks": excluded,
        },
        "domain_scope": {
            "banking_knowledge": {
                "reason": "banking_knowledge environment rejects solo mode"
            }
        },
        "harness_integrity": {
            "model_sent_to_litellm": "openai/test/model",
            "request_timeout": 60.0,
            "litellm_num_retries": 0,
            "max_tokens": 16384,
        },
    }


def raw_results(tasks, simulations):
    return {
        "info": {
            "agent_info": {
                "implementation": "llm_agent_solo",
                "llm": "openai/test/model",
                "llm_args": {"timeout": 60.0, "num_retries": 0, "max_tokens": 16384},
            },
            "user_info": {"implementation": "dummy_user"},
        },
        "tasks": tasks,
        "simulations": simulations,
    }


class TauBenchScoringTests(unittest.TestCase):
    def test_task_with_real_nl_assertions_is_never_scored(self):
        """nl_assertions 에 **내용이 있으면** 판정이 필요하므로 채점하지 않는다."""
        for basis in (["DB", "NL_ASSERTION"], ["ENV_ASSERTION", "ACTION", "NL_ASSERTION"]):
            with self.subTest(basis=basis):
                status, reason = scorer.classify_task(
                    task("t", basis, ["에이전트는 정책을 지켜야 한다"])
                )
                self.assertEqual("not_measured", status)
                self.assertEqual("llm_judge_required", reason)

        raw = raw_results(
            [task("judge-task", ["DB", "NL_ASSERTION"], ["에이전트는 정책을 지켜야 한다"])],
            [simulation("judge-task", 1.0)],
        )
        scored = scorer.score_domain("retail", raw, runnable_tasks=1)
        self.assertEqual(0, scored["measured"])

    def test_declared_nl_assertion_without_content_is_scored(self):
        """retail test 40건 중 28건이 NL_ASSERTION 을 선언만 하고 내용이 없다.
        이걸 버리면 실행한 29건이 0건 측정으로 집계된다 (2026-08-23 실제 발생)."""
        status, reason = scorer.classify_task(task("t", ["DB", "NL_ASSERTION"]))
        self.assertEqual("measured", status)
        self.assertIsNone(reason)

        raw = raw_results(
            [task("free", ["DB", "NL_ASSERTION"])],
            [simulation("free", 1.0)],
        )
        scored = scorer.score_domain("retail", raw, runnable_tasks=1)
        self.assertEqual(1, scored["measured"])
        self.assertEqual(1, scored["passed"])

    def test_communicate_alone_is_scored(self):
        """evaluator_communicate.py 는 부분문자열 매칭이다 — 판정이 아니다."""
        status, _ = scorer.classify_task(task("t", ["DB", "COMMUNICATE"]))
        self.assertEqual("measured", status)

    def test_run_domain_result_is_not_overwritten_by_fallback(self):
        """retail 을 실행하면 그 결과가 하드코딩 not_measured 로 덮이면 안 된다."""
        raw = raw_results(
            [task("r1", ["DB"])],
            [simulation("r1", 1.0)],
        )
        m = manifest(["r1"])
        m["split"]["domain"] = "retail"
        summary = scorer.build_summary({"retail": raw}, m, "taubench")
        self.assertEqual(1, summary["by_domain"]["retail"]["measured"])
        self.assertEqual("not_measured", summary["by_domain"]["telecom"]["status"])
        self.assertIsNone(summary["by_domain"]["telecom"]["pass_rate"])

    def test_default_split_resolves_ids_from_split_tasks_json(self):
        split_ids = ["test-c", "test-a", "test-b"]
        tasks = [task(value, ["ENV_ASSERTION"]) for value in reversed(split_ids)]
        with tempfile.TemporaryDirectory() as temp_dir:
            split_path = Path(temp_dir) / "split_tasks.json"
            split_path.write_text(
                json.dumps({"small": ["test-a"], "test": split_ids}),
                encoding="utf-8",
            )
            with mock.patch.dict(os.environ, {}, clear=True):
                args = runner.parse_args(["--model", "test/model"])
            resolved = runner.resolve_task_split(tasks, split_path, args.split)

        self.assertEqual("test", args.split)
        self.assertEqual(split_ids, resolved["task_ids"])
        self.assertEqual(len(split_ids), resolved["task_count"])

        with mock.patch.dict(os.environ, {"TAUBENCH_SPLIT": "small"}, clear=True):
            overridden = runner.parse_args(["--model", "test/model"])
        self.assertEqual("small", overridden.split)

    def test_unknown_split_names_available_splits(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            split_path = Path(temp_dir) / "split_tasks.json"
            split_path.write_text(
                json.dumps({"train": ["a"], "test": ["b"], "base": ["c"]}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                ValueError, "available splits: base, test, train"
            ):
                runner.resolve_task_split([], split_path, "missing")

    def test_litellm_args_disable_retries_and_omit_temperature(self):
        args = runner.build_litellm_args("http://host/v1", 12.5, 4096)
        self.assertEqual(0, args["num_retries"])
        self.assertEqual(12.5, args["timeout"])
        self.assertNotIn("temperature", args)

    def test_split_name_and_task_count_are_recorded_in_summary(self):
        ids = ["a", "b", "c"]
        raw = raw_results(
            [task(value, ["ENV_ASSERTION"]) for value in ids],
            [simulation(value, 1.0) for value in ids],
        )
        summary = scorer.build_summary({"telecom": raw}, manifest(ids), "taubench")
        self.assertEqual("test", summary["split"]["name"])
        self.assertEqual(3, summary["split"]["task_count"])
        self.assertEqual(ids, summary["split"]["task_ids"])


    def test_nl_assertion_declared_but_empty_needs_no_judge(self):
        """retail test 40건 중 39건이 NL_ASSERTION 을 선언하지만 실제 내용은 11건뿐이다.
        선언만 보고 배제하면 29건을 잘못 버린다 (evaluator_nl_assertions.py:37 이
        빈 목록에 대해 판정 없이 1.0 을 돌려준다)."""
        declared_empty = task("declared_empty", ["DB", "NL_ASSERTION"])
        self.assertFalse(runner.requires_judge(declared_empty))

    def test_nl_assertion_with_content_needs_judge(self):
        with_content = task("real", ["DB", "NL_ASSERTION"], ["에이전트는 정책을 지켜야 한다"])
        self.assertTrue(runner.requires_judge(with_content))

    def test_communicate_is_not_a_judge_basis(self):
        """evaluator_communicate.py 는 부분문자열 매칭이다 — 판정 모델이 아니다."""
        comm = task("comm", ["DB", "COMMUNICATE"])
        self.assertFalse(runner.requires_judge(comm))

    def test_telecom_bases_remain_judge_free(self):
        """이 규칙 도입으로 telecom 거동이 바뀌면 안 된다."""
        for basis in (["ENV_ASSERTION"], ["ACTION", "ENV_ASSERTION"]):
            self.assertFalse(runner.requires_judge(task("t", basis)))

    def test_selected_judge_task_is_reported_not_measured_with_count(self):
        runnable = task("programmatic", ["ENV_ASSERTION"])
        judge = task("judge", ["DB", "NL_ASSERTION"], ["에이전트는 보상을 먼저 제안하면 안 된다"])
        with tempfile.TemporaryDirectory() as temp_dir:
            split_path = Path(temp_dir) / "split_tasks.json"
            split_path.write_text(
                json.dumps({"test": ["programmatic", "judge"]}), encoding="utf-8"
            )
            split = runner.resolve_task_split([runnable, judge], split_path, "test")

        raw = raw_results([runnable], [simulation("programmatic", 1.0)])
        run_manifest = manifest(
            split["task_ids"],
            task_count=split["task_count"],
            not_measured_tasks=split["not_measured_tasks"],
        )
        summary = scorer.build_summary({"telecom": raw}, run_manifest, "taubench")
        excluded = summary["not_measured"]["selected_split"]
        self.assertEqual(1, excluded["count"])
        self.assertEqual("judge", excluded["tasks"][0]["task_id"])
        self.assertEqual("llm_judge_required", excluded["tasks"][0]["reason"])

    def test_upstream_task_ids_exactly_match_summary_task_ids(self):
        ids = ["first", "second", "third"]
        args = runner.parse_args(["--model", "test/model", "--split", "test"])
        llm_args = runner.build_litellm_args("http://host/v1", 60.0, 16384)
        command = runner.build_upstream_command(
            args,
            llm_args,
            llm_args,  # user_llm_args — solo 모드라 사용되지 않는다
            Path("upstream"),
            ids,
        )
        start = command.index("--task-ids") + 1
        end = command.index("--num-trials")
        passed_upstream = command[start:end]
        raw = raw_results(
            [task(value, ["ENV_ASSERTION"]) for value in ids],
            [simulation(value, 1.0) for value in ids],
        )
        summary = scorer.build_summary({"telecom": raw}, manifest(ids), "taubench")

        self.assertIn("--task-split-name", command)
        self.assertEqual("test", command[command.index("--task-split-name") + 1])
        self.assertEqual(summary["split"]["task_ids"], passed_upstream)

    def test_pass_rate_uses_upstream_result_reward(self):
        # 평가 조건의 세부 내용은 없고 upstream reward만 결과를 결정한다.
        raw = raw_results(
            [
                task("upstream-pass", ["ENV_ASSERTION"]),
                task("upstream-fail", ["ENV_ASSERTION"]),
            ],
            [
                simulation("upstream-pass", 1.0),
                simulation("upstream-fail", 0.0),
            ],
        )
        scored = scorer.score_domain("telecom", raw, runnable_tasks=2)
        self.assertEqual(0.5, scored["pass_rate"])
        self.assertEqual(1, scored["passed"])
        self.assertEqual(1, scored["failed"])
        self.assertIn("reward_info.reward", scored["pass_rate_source"])

    def test_zero_runnable_domain_is_explicit(self):
        scored = scorer.score_domain(
            "banking_knowledge", None, 0, "no-user mode unsupported"
        )
        self.assertEqual("not_measured", scored["status"])
        self.assertEqual("no-user mode unsupported", scored["reason"])
        self.assertEqual(0, scored["runnable_tasks"])
        self.assertIsNone(scored["pass_rate"])




class PublishGateTest(unittest.TestCase):
    """발행 게이트. 2026-08-19 에 telecom 40/40 이 infrastructure_error 로 죽었는데도
    파이프라인 전체가 exit 0 으로 성공처럼 보인 사고를 막는다."""

    def _summary(self, telecom):
        return {
            "overall": {"pass_rate": None, "measured": 0},
            "by_domain": {"telecom": telecom},
        }

    def test_all_infrastructure_errors_blocks_publish(self):
        failures, _ = scorer.validate_summary(
            self._summary(
                {
                    "status": "not_measured",
                    "reason": "no upstream records had a runnable numeric reward",
                    "runnable_tasks": 40,
                    "measured": 0,
                    "termination_reasons": {"infrastructure_error": 40},
                }
            )
        )
        self.assertTrue(failures)
        # 게이트 문구는 "완주 실패 N건 (귀책 내역)" 이다. 귀책을 단정하지 않는다.
        self.assertTrue(any("완주 실패" in f for f in failures), failures)

    def test_out_of_scope_domains_are_not_failures(self):
        """retail/airline 은 판정 모델이 없어 의도적으로 비운다. 장애가 아니다."""
        failures, _ = scorer.validate_summary(
            {
                "overall": {"pass_rate": 0.5, "measured": 40},
                "by_domain": {
                    "telecom": {
                        "status": "measured",
                        "runnable_tasks": 40,
                        "measured": 40,
                        "termination_reasons": {},
                    },
                    "retail": {
                        "status": "not_measured",
                        "reason": "LLM judge required",
                        "runnable_tasks": 0,
                        "measured": 0,
                    },
                },
            }
        )
        self.assertEqual(failures, [])

    def test_partial_coverage_blocks_publish(self):
        failures, _ = scorer.validate_summary(
            {
                "overall": {"pass_rate": 0.5, "measured": 20},
                "by_domain": {
                    "telecom": {
                        "status": "measured",
                        "runnable_tasks": 40,
                        "measured": 20,
                        "termination_reasons": {},
                    }
                },
            }
        )
        self.assertTrue(any("부분 실행" in f for f in failures))


class IncompletionAttributionTest(unittest.TestCase):
    """완주 실패를 후보/환경/미분류 3상태로 가른다.

    tau2 는 셋을 모두 termination_reason=infrastructure_error 로 묶는다. 구분하지 않으면
    서버가 죽은 런이 나쁜 모델 점수로 발행된다 — 2026-08-20 에 실제로 있었다.
    error_type 만으로도 부족하다: ContextWindowExceededError 는 후보 에이전트에서도
    사용자 시뮬레이터에서도 날 수 있고, 후자는 평가 대상의 결함이 아니다.
    """

    AGENT_TB = "agent_msg, self.agent_state = self.agent.generate_next_message(\n"
    USER_TB = "user_msg, self.user_state = self.user.generate_next_message(\n"

    def _sim(self, reason, error_type=None, traceback=None, reward=None):
        s = {"termination_reason": reason}
        info = {}
        if error_type:
            info["error_type"] = error_type
        if traceback:
            info["error_traceback"] = traceback
        if info:
            s["info"] = info
        if reward is not None:
            s["reward_info"] = {"reward": reward}
        return s

    def test_context_overflow_in_agent_is_candidate(self):
        c, e, u = scorer._classify_incompletions(
            [self._sim("infrastructure_error", "ContextWindowExceededError", self.AGENT_TB)]
        )
        self.assertEqual(dict(c), {"ContextWindowExceededError@agent": 1})
        self.assertEqual(dict(e), {})
        self.assertEqual(dict(u), {})

    def test_context_overflow_in_user_is_not_candidate(self):
        """사용자 시뮬레이터가 컨텍스트를 넘긴 것은 평가 대상 탓이 아니다."""
        c, e, u = scorer._classify_incompletions(
            [self._sim("infrastructure_error", "ContextWindowExceededError", self.USER_TB)]
        )
        self.assertEqual(dict(c), {})
        self.assertEqual(dict(e), {"ContextWindowExceededError@user": 1})

    def test_context_overflow_without_traceback_is_unclassified(self):
        """actor 를 모르면 후보에게 씌우지 않는다."""
        c, e, u = scorer._classify_incompletions(
            [self._sim("infrastructure_error", "ContextWindowExceededError")]
        )
        self.assertEqual(dict(c), {})
        self.assertEqual(dict(u), {"ContextWindowExceededError@unknown": 1})

    def test_known_environment_errors(self):
        sims = [
            self._sim("infrastructure_error", t, self.AGENT_TB)
            for t in ("Timeout", "InternalServerError", "APIError", "TypeError", "BadRequestError")
        ]
        c, e, u = scorer._classify_incompletions(sims)
        self.assertEqual(dict(c), {})
        self.assertEqual(len(e), 5)
        self.assertEqual(dict(u), {})

    def test_unknown_error_type_is_unclassified_not_environment(self):
        """모르는 것을 '환경 탓' 이라 단정하는 것도 근거 없는 주장이다."""
        c, e, u = scorer._classify_incompletions(
            [self._sim("infrastructure_error", "SomeFutureUpstreamError", self.AGENT_TB)]
        )
        self.assertEqual(dict(c), {})
        self.assertEqual(dict(e), {})
        self.assertEqual(dict(u), {"SomeFutureUpstreamError@agent": 1})

    def test_normal_termination_is_not_an_incompletion(self):
        c, e, u = scorer._classify_incompletions(
            [self._sim("user_stop", reward=1.0), self._sim("max_steps", reward=0.0)]
        )
        self.assertEqual((dict(c), dict(e), dict(u)), ({}, {}, {}))


class SecretLeakTest(unittest.TestCase):
    """자격증명이 산출물에 들어가지 않는지 못 박는다.

    tau2 는 llm_args 를 results.json 에 그대로 적는다. 2026-08-23 에 API 키를
    llm_args 로 넘겨 142개 파일에 박혔고 GitHub 푸시 보호가 두 번 막았다.
    """

    def test_redactor_scrubs_nested_api_key(self):
        node = {
            "info": {
                "agent_info": {"llm_args": {"api_key": "sk-secret", "timeout": 60}},
                "user_info": {"llm_args": {"api_key": "sk-secret"}},
            },
            "simulations": [{"llm_args": {"api_key": "sk-secret"}}],
        }
        changed = runner._scrub_api_key(node)
        self.assertTrue(changed)
        dumped = json.dumps(node)
        self.assertNotIn("sk-secret", dumped)
        self.assertEqual(3, dumped.count("***REDACTED***"))
        # 다른 필드는 건드리지 않는다
        self.assertEqual(60, node["info"]["agent_info"]["llm_args"]["timeout"])

    def test_redactor_reports_no_change_when_clean(self):
        node = {"info": {"agent_info": {"llm_args": {"timeout": 60}}}}
        self.assertFalse(runner._scrub_api_key(node))

    def test_external_user_simulator_requires_key_env(self):
        """키를 인자로 받지 않으므로, 없으면 실행 전에 죽어야 한다."""
        args = runner.parse_args(
            [
                "--model", "local-model",
                "--base-url", "http://host/v1/chat/completions",
                "--track-name", "taubench",
                "--mode", "standard",
                "--user-model", "openrouter/openai/gpt-4.1-mini",
            ]
        )
        self.assertEqual("openrouter/openai/gpt-4.1-mini", args.user_model)
        self.assertEqual("TAUBENCH_USER_API_KEY", args.user_api_key_env)

    def test_api_key_is_not_a_cli_argument(self):
        """키가 CLI 인자면 ps 로 노출된다. 이름만 받아야 한다."""
        args = runner.parse_args(
            ["--model", "m", "--base-url", "http://h/v1/chat/completions", "--track-name", "t"]
        )
        for name in vars(args):
            self.assertNotIn(
                name, {"user_api_key", "api_key"}, "키 값을 받는 인자가 있으면 안 된다"
            )


def _integrity_fixture(user_timeout, user_max_tokens, declared=None):
    manifest = {
        "harness_integrity": {
            "agent_implementation": "llm_agent",
            "user_implementation": "user_simulator",
            "model_sent_to_litellm": "openai/candidate",
            "request_timeout": 60.0,
            "max_tokens": 16384,
            **(declared or {}),
        }
    }
    raw = {
        "info": {
            "agent_info": {
                "implementation": "llm_agent",
                "llm": "openai/candidate",
                "llm_args": {"timeout": 60.0, "num_retries": 0, "max_tokens": 16384},
            },
            "user_info": {
                "implementation": "user_simulator",
                "llm": "openrouter/openai/gpt-4.1-mini",
                "llm_args": {"timeout": user_timeout, "max_tokens": user_max_tokens},
            },
        }
    }
    return raw, manifest


class TestUserSimulatorProtocol(unittest.TestCase):
    """두 모델을 비교하려면 후보만 달라야 한다 — 사용자 프로토콜은 같아야 한다."""

    def test_declared_user_protocol_must_match_what_actually_ran(self):
        declared = {"user_request_timeout": 120.0, "user_max_tokens": 16384}
        raw, manifest = _integrity_fixture(120.0, 16384, declared)
        result = scorer._validate_upstream_integrity(raw, manifest)
        self.assertTrue(result["user_protocol"]["pinned"])

        # 불일치는 예외가 아니라 기록이다. build_summary 안에서 터지면 main 이
        # exit 2 로 끝나 summary.json 을 아예 남기지 않는데, 이 트랙의 원칙은
        # "발행 불가여도 산출물은 남긴다" 이다.
        raw, manifest = _integrity_fixture(600.0, 8192, declared)
        protocol = scorer._validate_upstream_integrity(raw, manifest)["user_protocol"]
        self.assertEqual(protocol["mismatch"]["declared"]["user_request_timeout"], 120.0)
        self.assertEqual(protocol["mismatch"]["observed"]["user_request_timeout"], 600.0)

        summary = {
            "overall": {"pass_rate": 0.5, "measured": 1},
            "split": {"domain": "telecom", "task_count": 1},
            "by_domain": {"telecom": {"status": "measured", "runnable_tasks": 1,
                                      "measured": 1, "termination_reasons": {}}},
            "harness_integrity": {"upstream_result_evidence": {"user_protocol": protocol}},
        }
        failures, _ = scorer.validate_summary(summary)
        self.assertTrue(any("비교할 수 없다" in f for f in failures))

    def test_legacy_artifacts_pass_but_are_marked_unpinned(self):
        """구버전 런은 사용자 인자를 기록하지 않는다. 거부하지 않되 증거 없음을 남긴다."""

        raw, manifest = _integrity_fixture(600.0, 8192)
        protocol = scorer._validate_upstream_integrity(raw, manifest)["user_protocol"]
        self.assertFalse(protocol["pinned"])
        self.assertEqual(protocol["user_request_timeout"], 600.0)
        self.assertIn("증거가 없다", protocol["reason"])


class TestOfficialCoverage(unittest.TestCase):
    """완주와 '도메인을 다 쟀다'는 다르다.

    retail test 는 40건 중 29건만 판정 없이 채점된다. 29/29 를 끝냈다는 이유로
    'retail' 이라는 이름을 달면 공식 split 성적으로 읽힌다.
    """

    @staticmethod
    def _summary(domain, official, runnable, measured):
        eligible = runnable == official
        coverage = {"measured": measured, "runnable_task_count": runnable,
                    "official_task_count": official}
        if not eligible:
            coverage["reason"] = "판정 불필요 부분집합만 측정했다 — 공식 도메인 점수가 아니다"
        return {
            "overall": {"pass_rate": 0.5, "measured": measured},
            "split": {"domain": domain, "task_count": official},
            "by_domain": {
                domain: {
                    "status": "measured",
                    "runnable_tasks": runnable,
                    "measured": measured,
                    "termination_reasons": {},
                    "benchmark_eligible": eligible,
                    "coverage": coverage,
                }
            },
        }

    def test_a_judge_free_subset_is_not_the_domain_score(self):
        summary = self._summary("retail", official=40, runnable=29, measured=29)
        failures, warnings = scorer.validate_summary(summary)
        self.assertEqual(failures, [])          # 유효한 측정이다 — 거부하지 않는다
        self.assertTrue(any("부분집합 점수로만" in w for w in warnings))

    def test_full_official_coverage_is_eligible(self):
        summary = self._summary("telecom", official=40, runnable=40, measured=40)
        failures, warnings = scorer.validate_summary(summary)
        self.assertEqual(failures, [])
        self.assertEqual(warnings, [])

    def test_build_summary_is_what_marks_eligibility(self):
        """검증 함수가 요약을 변형하면 계산과 판정의 경계가 흐려진다."""

        summary = self._summary("retail", official=40, runnable=29, measured=29)
        del summary["by_domain"]["retail"]["benchmark_eligible"]
        del summary["by_domain"]["retail"]["coverage"]
        scorer.validate_summary(summary)
        self.assertNotIn("benchmark_eligible", summary["by_domain"]["retail"])


cohort = load_module("taubench_cohort_test", TAUBENCH_DIR / "scoring" / "cohort.py")


def _run(session, candidate, user_model, passed, *, user_timeout=None, user_max_tokens=None,
         domain="telecom", split_name="test", task_ids=("t1", "t2", "t3")):
    return {
        "_session": session,
        "benchmark": "tau2",
        "scoring_version": "taubench_state_v1",
        "model": candidate,
        "split": {"domain": domain, "name": split_name, "task_count": len(task_ids),
                  "runnable_task_count": len(task_ids), "task_ids": list(task_ids)},
        "harness_integrity": {
            "mode": "standard", "agent_implementation": "llm_agent",
            "user_implementation": "user_simulator", "user_model_sent_to_litellm": user_model,
            "user_request_timeout": user_timeout, "user_max_tokens": user_max_tokens,
            "max_steps": 100, "tau2_version": "1.0.1",
            "model_sent_to_litellm": f"openai/{candidate}",
        },
        "by_domain": {domain: {"task_results": [
            {"task_id": t, "passed": t in passed} for t in task_ids]}},
    }


class TestCohortKeys(unittest.TestCase):
    def test_candidate_is_excluded_from_the_comparison_fingerprint(self):
        """후보가 지문에 들어가면 모든 모델이 자기만의 코호트가 되어 비교가 사라진다."""

        a = _run("s1", "modelA", "openai/gpt-4.1-mini", {"t1"}, user_timeout=120.0, user_max_tokens=16384)
        b = _run("s2", "modelB", "openai/gpt-4.1-mini", {"t2"}, user_timeout=120.0, user_max_tokens=16384)
        self.assertEqual(
            cohort.comparison_fingerprint(a)["fingerprint"],
            cohort.comparison_fingerprint(b)["fingerprint"],
        )

    def test_a_different_user_simulator_is_a_different_protocol(self):
        """사용자 시뮬레이터 교체로 같은 모델이 0.475 -> 0.900 이 된 전례가 있다."""

        a = _run("s1", "m", "openai/gpt-4.1-mini", {"t1"}, user_timeout=120.0, user_max_tokens=16384)
        b = _run("s2", "m", "openai/m", {"t1"}, user_timeout=120.0, user_max_tokens=16384)
        self.assertNotEqual(
            cohort.comparison_fingerprint(a)["fingerprint"],
            cohort.comparison_fingerprint(b)["fingerprint"],
        )

    def test_unrecorded_user_args_block_cross_candidate_comparison(self):
        legacy = _run("s1", "m", "openai/gpt-4.1-mini", {"t1"})
        pinned = _run("s2", "m", "openai/gpt-4.1-mini", {"t1"}, user_timeout=120.0, user_max_tokens=16384)
        self.assertFalse(cohort.comparison_fingerprint(legacy)["comparable_across_candidates"])
        self.assertTrue(cohort.comparison_fingerprint(pinned)["comparable_across_candidates"])

    def test_pinning_status_does_not_split_replicates(self):
        """고정 여부를 지문에 섞으면 같은 모델의 반복 실행끼리 갈라진다."""

        runs = [_run(f"rep{i}", "m", "openai/gpt-4.1-mini", {"t1"}) for i in range(3)]
        keys = {cohort.replicate_key(r) for r in runs}
        self.assertEqual(len(keys), 1)

    def test_reproducibility_compares_sets_not_counts(self):
        same = [_run(f"r{i}", "m", "openai/u", {"t1", "t2"}) for i in range(2)]
        report = cohort.reproducibility_report(same)
        self.assertEqual(report[0]["status"], "IDENTICAL")

        swapped = [_run("r1", "m", "openai/u", {"t1", "t2"}),
                   _run("r2", "m", "openai/u", {"t1", "t3"})]
        report = cohort.reproducibility_report(swapped)
        self.assertEqual(report[0]["status"], "DIVERGED")
        self.assertEqual(report[0]["passed_counts"], [2, 2])   # 건수는 같다
        self.assertEqual(report[0]["unstable_tasks"], ["t2", "t3"])

    def test_a_single_run_is_unverified_not_passing(self):
        report = cohort.reproducibility_report([_run("only", "m", "openai/u", {"t1"})])
        self.assertEqual(report[0]["status"], "UNVERIFIED")


class TestUserProtocolP0(unittest.TestCase):
    """terra 검토(01a03eb1)에서 나온 P0 두 건."""

    def test_a_swapped_user_model_is_a_mismatch(self):
        """인자만 대조하면 시뮬레이터가 통째로 바뀌어도 통과한다."""

        declared = {"user_request_timeout": 120.0, "user_max_tokens": 16384}
        raw, manifest = _integrity_fixture(120.0, 16384, declared)
        manifest["harness_integrity"]["user_model_sent_to_litellm"] = "openai/some-other-user"
        protocol = scorer._validate_upstream_integrity(raw, manifest)["user_protocol"]
        self.assertIn("mismatch", protocol)
        self.assertEqual(protocol["mismatch"]["observed"]["user_model"],
                         "openrouter/openai/gpt-4.1-mini")

    def test_a_recorded_mismatch_blocks_cross_candidate_comparison(self):
        """채점기는 upstream_result_evidence 아래에 쓴다 — 위치를 잘못 읽으면 항상 통과한다."""

        run = _run("s1", "m", "openai/gpt-4.1-mini", {"t1"},
                   user_timeout=120.0, user_max_tokens=16384)
        self.assertTrue(cohort.comparison_fingerprint(run)["comparable_across_candidates"])

        run["harness_integrity"]["upstream_result_evidence"] = {
            "user_protocol": {"pinned": True, "mismatch": {"declared": {}, "observed": {}}}
        }
        result = cohort.comparison_fingerprint(run)
        self.assertFalse(result["comparable_across_candidates"])
        self.assertIn("실제 실행이 다르다", result["reason"])


class TestReviewFollowups(unittest.TestCase):
    """terra(01a03eb1) / luna(01a03eb3) 검토에서 나온 나머지."""

    def test_multi_trial_summaries_are_not_judged_by_set_equality(self):
        """1/4 통과와 4/4 통과가 같은 집합이 된다 — Pass^k 를 대신할 수 없다."""

        run = _run("s1", "m", "openai/u", {"t1"})
        run["by_domain"]["telecom"]["task_results"] = [
            {"task_id": "t1", "passed": True},
            {"task_id": "t1", "passed": False},      # 같은 과제의 2회차
            {"task_id": "t2", "passed": False},
        ]
        self.assertTrue(cohort.is_multi_trial(run))
        report = cohort.reproducibility_report([run, run])
        self.assertEqual(report[0]["status"], "UNSUPPORTED")

    def test_single_trial_is_still_compared(self):
        runs = [_run(f"r{i}", "m", "openai/u", {"t1"}) for i in range(2)]
        self.assertFalse(cohort.is_multi_trial(runs[0]))
        self.assertEqual(cohort.reproducibility_report(runs)[0]["status"], "IDENTICAL")

    def test_an_unpinned_run_warns_that_it_cannot_be_compared(self):
        summary = {
            "overall": {"pass_rate": 0.5, "measured": 1},
            "split": {"domain": "telecom", "task_count": 1},
            "by_domain": {"telecom": {"status": "measured", "runnable_tasks": 1,
                                      "measured": 1, "termination_reasons": {}}},
            "harness_integrity": {"upstream_result_evidence": {
                "user_protocol": {"pinned": False, "reason": "구버전"}}},
        }
        failures, warnings = scorer.validate_summary(summary)
        self.assertEqual(failures, [])
        self.assertTrue(any("모델 간 비교에 쓸 수 없다" in w for w in warnings))


reporter = load_module("taubench_report_test", TAUBENCH_DIR / "scoring" / "report.py")


class TestReportEnforcement(unittest.TestCase):
    """플래그를 읽는 코드가 없으면 플래그는 아무것도 막지 못한다."""

    @staticmethod
    def _summary(model, *, official=40, runnable=40, publishable=True, pinned=True):
        run = _run("s", model, "openai/gpt-4.1-mini", {"t1"},
                   user_timeout=120.0 if pinned else None,
                   user_max_tokens=16384 if pinned else None)
        run["split"].update({"task_count": official, "runnable_task_count": runnable})
        run["by_domain"]["telecom"].update({
            "pass_rate": 0.5, "passed": 1, "measured": 2, "runnable_tasks": runnable,
        })
        run["publish_status"] = {"publishable": publishable}
        return run

    def test_a_subset_never_carries_the_domain_name(self):
        markdown = reporter.render_markdown([self._summary("m", runnable=29)], [])
        self.assertIn("telecom/test/judge-free-29", markdown)
        self.assertIn("공식 split 부분집합", markdown)

    def test_eligibility_is_recomputed_when_the_artifact_predates_the_flag(self):
        """보고 계층이 재채점을 전제하면 강제가 조용히 풀린다."""

        run = self._summary("m", runnable=29)
        self.assertNotIn("benchmark_eligible", run["by_domain"]["telecom"])
        _, entry = reporter._domain_entry(run)
        self.assertFalse(entry["benchmark_eligible"])

    def test_an_unpinned_cohort_is_marked_uncomparable(self):
        runs = [self._summary("a", pinned=False), self._summary("b", pinned=False)]
        markdown = reporter.render_markdown(runs, [])
        self.assertIn("UNCOMPARABLE", markdown)
        self.assertIn("사용자 프로토콜 미고정", markdown)

    def test_a_pinned_publishable_cohort_has_no_exclusion_reason(self):
        runs = [self._summary("a"), self._summary("b")]
        markdown = reporter.render_markdown(runs, [])
        self.assertNotIn("UNCOMPARABLE", markdown)

    def test_a_rejected_run_never_shows_its_number(self):
        markdown = reporter.render_markdown([self._summary("m", publishable=False)], [])
        self.assertIn("발행 불가", markdown)
        self.assertNotIn("50.00", markdown)


class TestResultsPathCasing(unittest.TestCase):
    """문자열 치환만 하면 리눅스에서 한 런의 산출물이 두 디렉토리로 갈린다."""

    def test_an_existing_directory_spelling_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "results" / "Google_Gemma_4_26B_A4B_it").mkdir(parents=True)
            resolved = runner.results_model_dir_name(base, "google/gemma-4-26b-a4b-it")
            self.assertEqual(resolved, "Google_Gemma_4_26B_A4B_it")

    def test_a_new_model_keeps_its_normalized_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "results").mkdir()
            self.assertEqual(runner.results_model_dir_name(base, "new/model:v1"), "new_model_v1")

    def test_ambiguous_casing_is_rejected_rather_than_guessed(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            try:
                for name in ("model_a", "MODEL_A"):
                    (base / "results" / name).mkdir(parents=True)
            except FileExistsError:
                self.skipTest("case-insensitive filesystem cannot hold both spellings")
            with self.assertRaises(ValueError):
                runner.results_model_dir_name(base, "model/a")


passk = load_module("taubench_passk_test", TAUBENCH_DIR / "scoring" / "passk.py")


class TestPassHatK(unittest.TestCase):
    """정의는 상류(agent_metrics.pass_hat_k)를 그대로 따른다."""

    @staticmethod
    def _results(spec):
        """spec = {task_id: [통과여부, ...]} — 시행 순서대로."""
        out = []
        for task_id, outcomes in spec.items():
            for passed in outcomes:
                out.append({"task_id": task_id, "evaluation_status": "measured",
                            "passed": passed})
        return out

    def test_a_task_passed_once_of_two_scores_zero_at_k2(self):
        table = passk.pass_hat_k_table(self._results({"a": [True, False]}))
        self.assertEqual(table["pass_hat_k"]["pass^1"], 0.5)
        self.assertEqual(table["pass_hat_k"]["pass^2"], 0.0)

    def test_always_passing_stays_one_at_every_k(self):
        table = passk.pass_hat_k_table(self._results({"a": [True, True, True]}))
        self.assertEqual(table["pass_hat_k"]["pass^3"], 1.0)

    def test_max_k_follows_the_least_repeated_task(self):
        """4회 돌린 과제 하나 때문에 2회짜리 과제에 k=4 를 물을 수는 없다."""

        table = passk.pass_hat_k_table(self._results({"a": [True] * 4, "b": [True] * 2}))
        self.assertEqual(table["max_k"], 2)
        self.assertEqual(table["trials_per_task"], [2, 4])

    def test_unmeasured_trials_leave_the_denominator(self):
        """하네스 장애를 실패로 세면 모델 점수로 둔갑한다."""

        results = self._results({"a": [True, False]})
        results.append({"task_id": "a", "evaluation_status": "not_measured"})
        self.assertEqual(passk.task_success_counts(results)["a"], (1, 2))

    def test_no_measured_trials_yields_an_empty_table(self):
        table = passk.pass_hat_k_table([{"task_id": "a", "evaluation_status": "not_measured"}])
        self.assertEqual(table["max_k"], 0)
        self.assertEqual(table["pass_hat_k"], {})


if __name__ == "__main__":
    unittest.main()
