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


def task(task_id, basis):
    return {"id": task_id, "evaluation_criteria": {"reward_basis": basis}}


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

    def test_selected_judge_task_is_reported_not_measured_with_count(self):
        runnable = task("programmatic", ["ENV_ASSERTION"])
        judge = task("judge", ["DB", "NL_ASSERTION"])
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
        command = runner.build_upstream_command(
            args,
            runner.build_litellm_args("http://host/v1", 60.0, 16384),
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
        self.assertTrue(any("infrastructure_error" in f for f in failures))

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
