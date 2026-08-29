"""harness(KMMLU) 채점과 발행 게이트의 회귀 테스트."""

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

HARNESS_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = HARNESS_DIR.parents[2]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    sys.path.insert(0, str(Path(path).parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(Path(path).parent))
    return module


scorer = load_module("harness_score_under_test", HARNESS_DIR / "scoring" / "score_run.py")


def artifact(task, accuracy, *, items=1000, shot=5, version=2.0, lm_eval="0.4.12",
             configured="local-completions", maximum=4095, template="template", model_name="model"):
    return {
        "results": {task: {"sample_len": items, "acc,none": accuracy, "acc_stderr,none": 0.01}},
        "n-samples": {task: {"original": items, "effective": items}},
        "n-shot": {task: shot}, "versions": {task: version}, "lm_eval_version": lm_eval,
        "config": {"model": configured}, "max_length": maximum,
        "chat_template_sha": template, "model_name": model_name,
    }


def write_run(root, model, session, tasks):
    run = Path(root) / "results" / model / session / "language" / "harness"
    run.mkdir(parents=True, exist_ok=True)
    for task, payload in tasks.items():
        (run / f"{task}.json").write_text(json.dumps(payload), encoding="utf-8")
    return run


class RunnerTaskContractCannotDrift(unittest.TestCase):
    def test_subject_list_is_read_from_runner_not_copied(self):
        self.assertEqual(len(scorer.expected_tasks()), 45)
        source = (HARNESS_DIR / "scoring" / "score_run.py").read_text(encoding="utf-8")
        self.assertNotIn("kmmlu_accounting", source)


class AggregateUnitsCannotBeConflated(unittest.TestCase):
    def test_macro_and_item_weighted_average_keep_different_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = write_run(tmp, "m", "s", {"a": artifact("a", .8, items=100), "b": artifact("b", .4, items=900)})
            summary = scorer.build_summary(scorer.load_run(run), ["a", "b"])
        self.assertAlmostEqual(summary["macro"]["accuracy"], .6)
        self.assertAlmostEqual(summary["micro"]["accuracy"], .44)
        self.assertIsNotNone(summary["macro"]["stderr"])
        self.assertIsNotNone(summary["micro"]["stderr"])

    def test_single_subject_has_no_between_subject_standard_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = scorer.score_run(write_run(tmp, "m", "s", {"a": artifact("a", .5)}), ["a"])
        self.assertIsNone(summary["macro"]["stderr"])


class ProtocolGateCannotPublishAStitchedSession(unittest.TestCase):
    def test_mixed_five_and_zero_shot_blocks_full_coverage_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = write_run(tmp, "m", "s", {"a": artifact("a", .9, shot=5), "b": artifact("b", .7, shot=0)})
            summary = scorer.score_run(run, ["a", "b"])
        self.assertFalse(summary["publish_status"]["publishable"])
        self.assertTrue(any("n_shot" in failure for failure in summary["publish_status"]["failures"]))

    def test_protocol_failure_names_the_field_that_changed(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = write_run(tmp, "m", "s", {"a": artifact("a", .9, template="one"), "b": artifact("b", .7, template="two")})
            summary = scorer.score_run(run, ["a", "b"])
        self.assertTrue(any("chat_template_sha" in failure for failure in summary["publish_status"]["failures"]))

    def test_model_name_split_inside_directory_is_protocol_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = write_run(tmp, "m", "s", {"a": artifact("a", .9, model_name="one"), "b": artifact("b", .7, model_name="two")})
            summary = scorer.score_run(run, ["a", "b"])
        self.assertTrue(any("model_name" in failure for failure in summary["publish_status"]["failures"]))

    def test_missing_metric_is_not_mislabelled_as_coverage_loss(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = artifact("a", .9)
            del payload["results"]["a"]["acc,none"]
            summary = scorer.score_run(write_run(tmp, "m", "s", {"a": payload}), ["a"])
        self.assertTrue(any("메트릭 키" in failure for failure in summary["publish_status"]["failures"]))


class CoverageAndDuplicateRulesCannotHideRuns(unittest.TestCase):
    def test_incomplete_subject_set_is_not_publishable(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = scorer.score_run(write_run(tmp, "m", "s", {"a": artifact("a", .9)}), ["a", "b"])
        self.assertFalse(summary["publish_status"]["publishable"])
        self.assertTrue(any("과목 집합" in failure for failure in summary["publish_status"]["failures"]))

    def test_bad_suffix_without_twin_remains_a_coverage_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = scorer.score_run(write_run(tmp, "m", "s.bad", {"a": artifact("a", .9)}), ["a", "b"])
        self.assertFalse(summary["publish_status"]["publishable"])
        self.assertTrue(any("과목 집합" in failure for failure in summary["publish_status"]["failures"]))

    def test_digest_includes_protocol_not_just_accuracy_vector(self):
        with tempfile.TemporaryDirectory() as tmp:
            five = scorer.score_run(write_run(tmp, "m1", "s", {"a": artifact("a", .9, shot=5)}), ["a"])
            zero = scorer.score_run(write_run(tmp, "m2", "s", {"a": artifact("a", .9, shot=0)}), ["a"])
        self.assertNotEqual(scorer.measurement_digest(five), scorer.measurement_digest(zero))

    def test_subject_digest_checks_identity_not_only_subject_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            left = scorer.score_run(write_run(tmp, "m1", "s", {"a": artifact("a", .9)}), ["a"])
            right = scorer.score_run(write_run(tmp, "m2", "s", {"b": artifact("b", .9)}), ["b"])
        self.assertNotEqual(scorer.subject_set_digest(left), scorer.subject_set_digest(right))

    def test_bad_copy_loses_representative_tiebreak_only_after_same_digest(self):
        report = load_module("report_harness_under_test", REPO_ROOT / "report_harness_tracks.py")
        with tempfile.TemporaryDirectory() as tmp:
            good = scorer.score_run(write_run(tmp, "m", "s", {"a": artifact("a", .9)}), ["a"])
            bad = scorer.score_run(write_run(tmp, "m.bad", "s", {"a": artifact("a", .9)}), ["a"])
            kept, folded = report.dedupe([bad, good], scorer)
        self.assertEqual(kept[0]["source_path"], "m/s")
        self.assertEqual([entry["source_path"] for entry in folded], ["m.bad/s"])


class ReportNeverPlacesRejectedRunInPrimaryTable(unittest.TestCase):
    def test_rejected_numbers_stay_in_rejection_section(self):
        report = load_module("report_harness_for_rejection_test", REPO_ROOT / "report_harness_tracks.py")
        with tempfile.TemporaryDirectory() as tmp:
            summary = scorer.score_run(write_run(tmp, "m", "s", {"a": artifact("a", .9)}), ["a", "b"])
        text = report.render_markdown([summary], [], scorer)
        self.assertIn("발행하지 않은 런", text)
        self.assertIn("같은 축에 놓을 수 없다", text)
        self.assertNotIn("| `model` | `s` |", text)


class MissingProvenanceIsNotEvidenceOfSameness(unittest.TestCase):
    """필드가 통째로 없는 것과 값이 일치하는 것은 다르다.

    프로토콜 게이트는 디렉토리 안의 값이 서로 같은지만 본다. 전부 None 이면
    "일치"로 통과하지만, 기록이 없으면 그 프로토콜이 다른 런과 같았는지 감사할 수
    없다. 실측: chat_template_sha 가 통째로 없는 런이 4개이고 그중 2개가 표에
    실린다. 이번 작업 내내 지킨 규율과 같다 — 기록의 부재를 같음의 증거로 쓰지
    않는다.
    """

    def _summary(self, tmp, **overrides):
        payloads = {}
        for task in ("a", "b"):
            payload = artifact(task, 0.8)
            payload.update(overrides)
            payloads[task] = payload
        run = write_run(tmp, "m", "s", payloads)
        return scorer.score_run(run, ["a", "b"])

    def test_a_wholly_absent_protocol_field_warns_but_does_not_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = self._summary(tmp, chat_template_sha=None)
        status = summary["publish_status"]
        self.assertTrue(status["publishable"], status["failures"])
        self.assertTrue(
            any("chat_template_sha" in w and "감사할 수 없다" in w for w in status["warnings"]),
            status["warnings"],
        )

    def test_a_recorded_field_produces_no_such_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = self._summary(tmp, chat_template_sha="sha256:abc")
        self.assertFalse(
            any("chat_template_sha" in w for w in summary["publish_status"]["warnings"]),
            summary["publish_status"]["warnings"],
        )

    def test_the_report_degrades_instead_of_dying_when_claims_cannot_load(self):
        # 부가 계층을 못 읽는다고 수치 보고 전체가 죽으면, 사람들은 이 스크립트를
        # 건너뛰고 산출물을 직접 읽는다 — 게이트가 무력해진다.
        report = load_module("report_harness_degrade_test", REPO_ROOT / "report_harness_tracks.py")
        with tempfile.TemporaryDirectory() as tmp:
            summary = self._summary(tmp, chat_template_sha="sha256:abc")
            with contextlib.redirect_stderr(io.StringIO()):
                text = report.render_markdown([summary], [], scorer, Path(tmp))
        self.assertIn("KMMLU", text, "클레임을 못 읽어도 표는 나와야 한다")

    def test_the_report_renders_warnings_rather_than_swallowing_them(self):
        # 채점기가 경고를 내도 보고가 렌더링하지 않으면 독자에게는 없는 것과 같다.
        report = load_module("report_harness_warn_test", REPO_ROOT / "report_harness_tracks.py")
        with tempfile.TemporaryDirectory() as tmp:
            summary = self._summary(tmp, chat_template_sha=None)
            # base 는 실제 저장소여야 claims 계층을 찾는다.
            text = report.render_markdown([summary], [], scorer, HARNESS_DIR.parents[1])
        self.assertIn("발행하되 감사할 수 없는 것", text)
        self.assertIn("chat_template_sha", text)


if __name__ == "__main__":
    unittest.main()
