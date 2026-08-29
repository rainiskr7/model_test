"""harness(KMMLU) 채점 회귀 테스트.

이 트랙이 지키는 성질은 하나다 — **단일 100점 숫자를 만들지 않고, 다른 시험을
본 두 수를 같은 표에 올리지 않는다.**
"""

import importlib.util
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


def artifact(task, accuracy, items=1000, stderr=0.01, original=None):
    return {
        "results": {task: {
            "alias": task, "sample_len": items,
            "acc,none": accuracy, "acc_stderr,none": stderr,
        }},
        "n-samples": {task: {"original": original or items, "effective": items}},
        "n-shot": {task: 5},
    }


def write_run(root, model, session, tasks):
    run = Path(root) / "results" / model / session / "language" / "harness"
    run.mkdir(parents=True, exist_ok=True)
    for task, payload in tasks.items():
        (run / f"{task}_2026.json").write_text(json.dumps(payload), encoding="utf-8")
    return run


class TheExpectedSubjectListComesFromTheRunner(unittest.TestCase):
    def test_it_is_read_from_the_runner_not_copied(self):
        # 상수로 베끼면 러너와 채점기가 조용히 어긋난다.
        tasks = scorer.expected_tasks()
        self.assertGreater(len(tasks), 40)
        self.assertTrue(all(t.startswith("kmmlu_") for t in tasks), tasks[:3])
        source = (HARNESS_DIR / "scoring" / "score_run.py").read_text(encoding="utf-8")
        self.assertNotIn("kmmlu_accounting", source, "과목 목록을 채점기에 베꼈다")


class NoSingleHundredPointScore(unittest.TestCase):
    def test_the_summary_reports_two_means_with_their_own_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = write_run(tmp, "m", "s", {
                "a": artifact("a", 0.80, items=100),
                "b": artifact("b", 0.40, items=900),
            })
            summary = scorer.build_summary(scorer.load_run(run), ["a", "b"])
        # 과목 단위 평균과 문항 단위 평균은 다르다 — 하나로 접으면 그 사실이 사라진다.
        self.assertAlmostEqual(summary["macro"]["accuracy"], 0.60)
        self.assertAlmostEqual(summary["micro"]["accuracy"], (0.8 * 100 + 0.4 * 900) / 1000)
        self.assertIsNotNone(summary["macro"]["stderr"])
        self.assertIsNotNone(summary["micro"]["stderr"])

    def test_the_scorer_emits_no_composite_or_rank(self):
        source = (HARNESS_DIR / "scoring" / "score_run.py").read_text(encoding="utf-8")
        for forbidden in ("composite", "rank", "/ 100", "* 100"):
            self.assertNotIn(forbidden, source, f"점수를 만들고 있다: {forbidden}")

    def test_a_single_subject_run_has_no_macro_stderr(self):
        # 과목이 하나면 과목 간 산포를 잴 수 없다. 0 으로 적으면 완벽한 정밀도로 읽힌다.
        with tempfile.TemporaryDirectory() as tmp:
            run = write_run(tmp, "m", "s", {"a": artifact("a", 0.5)})
            summary = scorer.build_summary(scorer.load_run(run), ["a"])
        self.assertIsNone(summary["macro"]["stderr"])


class CoverageIsTheGate(unittest.TestCase):
    def test_an_incomplete_run_is_not_publishable(self):
        # 실측: 16과목 매크로 64.33 이 45과목 65.26 옆에 앉으면 "거의 비슷"으로
        # 읽히지만 다른 시험을 본 것이다.
        with tempfile.TemporaryDirectory() as tmp:
            run = write_run(tmp, "m", "s", {"a": artifact("a", 0.9)})
            summary = scorer.score_run(run, ["a", "b", "c"])
        self.assertFalse(summary["publish_status"]["publishable"])
        self.assertTrue(
            any("커버리지가 다르면" in f for f in summary["publish_status"]["failures"]),
            summary["publish_status"]["failures"],
        )

    def test_a_complete_run_is_publishable(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = write_run(tmp, "m", "s", {"a": artifact("a", 0.9), "b": artifact("b", 0.7)})
            summary = scorer.score_run(run, ["a", "b"])
        self.assertTrue(summary["publish_status"]["publishable"], summary["publish_status"])

    def test_an_unreadable_artifact_blocks_rather_than_shrinking_coverage(self):
        # 조용히 넘어가면 읽기 실패가 "덜 돌린 런"으로 둔갑한다.
        with tempfile.TemporaryDirectory() as tmp:
            run = write_run(tmp, "m", "s", {"a": artifact("a", 0.9), "b": artifact("b", 0.7)})
            (run / "broken_2026.json").write_text("{ 깨진", encoding="utf-8")
            summary = scorer.score_run(run, ["a", "b"])
        self.assertFalse(summary["publish_status"]["publishable"])
        self.assertTrue(any("읽지 못한" in f for f in summary["publish_status"]["failures"]))

    def test_a_partially_scored_subject_is_warned(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = write_run(tmp, "m", "s", {"a": artifact("a", 0.9, items=500, original=1000)})
            summary = scorer.score_run(run, ["a"])
        self.assertTrue(any("500/1000" in w for w in summary["publish_status"]["warnings"]))


class DuplicateArtifactsAreFoldedNotCounted(unittest.TestCase):
    def _summary(self, tmp, model, session):
        run = write_run(tmp, model, session, {"a": artifact("a", 0.9), "b": artifact("b", 0.7)})
        return scorer.score_run(run, ["a", "b"])

    def test_the_same_measurement_under_different_paths_shares_a_digest(self):
        # 실측: 한 모델의 동일 수치가 대소문자·접두사·`.bad` 때문에 네 줄로 나왔다.
        with tempfile.TemporaryDirectory() as tmp:
            a = self._summary(tmp, "gemma_4_31b_it", "s1")
            b = self._summary(tmp, "google_gemma_4_31B_it", "s1")
            c = self._summary(tmp, "gemma_4_31b_it.bad", "s1")
        self.assertEqual(scorer.measurement_digest(a), scorer.measurement_digest(b))
        self.assertEqual(scorer.measurement_digest(a), scorer.measurement_digest(c))
        self.assertEqual(len(scorer.group_duplicates([a, b, c])), 1)

    def test_a_different_measurement_keeps_its_own_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = self._summary(tmp, "m1", "s1")
            run = write_run(tmp, "m2", "s1", {"a": artifact("a", 0.5), "b": artifact("b", 0.7)})
            b = scorer.score_run(run, ["a", "b"])
        self.assertNotEqual(scorer.measurement_digest(a), scorer.measurement_digest(b))
        self.assertEqual(len(scorer.group_duplicates([a, b])), 2)


class TheReportSeparatesSamplingErrorFromReproducibility(unittest.TestCase):
    def _report(self):
        return load_module("report_harness_under_test", REPO_ROOT / "report_harness_tracks.py")

    def test_it_says_the_error_bar_is_not_reproducibility(self):
        # lm-eval 의 acc_stderr 는 문항 표집 오차다. 모델을 다시 돌렸을 때의 흔들림이
        # 아니다. 둘을 한 칸에 넣으면 재현성이 측정된 것처럼 읽힌다.
        with tempfile.TemporaryDirectory() as tmp:
            run = write_run(tmp, "m", "s", {"a": artifact("a", 0.9), "b": artifact("b", 0.7)})
            summary = scorer.score_run(run, ["a", "b"])
        text = self._report().render_markdown([summary], [])
        self.assertIn("표집 오차", text)
        self.assertIn("재현성", text)
        self.assertIn("재현성은 측정되지 않았다", text)

    def test_a_rejected_run_is_shown_but_never_in_the_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = write_run(tmp, "m", "s", {"a": artifact("a", 0.9)})
            summary = scorer.score_run(run, ["a", "b"])
        text = self._report().render_markdown([summary], [])
        self.assertIn("발행하지 않은 런", text)
        self.assertIn("같은 축에 놓을 수 없다", text)


if __name__ == "__main__":
    unittest.main()
