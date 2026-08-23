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
    def test_judge_reward_basis_is_never_scored(self):
        for basis in (
            ["DB", "NL_ASSERTION"],
            ["DB", "COMMUNICATE"],
            ["ENV_ASSERTION", "ACTION", "NL_ASSERTION"],
        ):
            with self.subTest(basis=basis):
                status, reason = scorer.classify_reward_basis(basis)
                self.assertEqual("not_measured", status)
                self.assertEqual("llm_judge_required", reason)

        raw = raw_results(
            [task("judge-task", ["DB", "NL_ASSERTION"])],
            [simulation("judge-task", 1.0)],
        )
        scored = scorer.score_domain("telecom", raw, runnable_tasks=1)
        self.assertEqual(0, scored["measured"])
        self.assertIsNone(scored["pass_rate"])

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


if __name__ == "__main__":
    unittest.main()


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
