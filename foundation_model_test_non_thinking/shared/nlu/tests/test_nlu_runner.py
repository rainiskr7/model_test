"""nlu 러너의 실행 무결성 회귀 테스트.

이 트랙은 채점기가 없다. 그래서 산출물이 **완전한 한 번의 시도인지** 를 산출물
스스로 말할 수 있어야 하고, 그것이 여기서 지키는 유일한 성질이다.
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


NLU_DIR = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


runner = load_module("nlu_runner_under_test", NLU_DIR / "nlu-gpustack.py")


class WrapperArgumentParsing(unittest.TestCase):
    """값이 빠진 옵션은 **끝나야** 한다."""

    def _run(self, *args, timeout=15):
        return subprocess.run(
            ["bash", str(NLU_DIR / "run_nlu.sh"), *args],
            capture_output=True, text=True, timeout=timeout,
        )

    def test_missing_option_value_exits_instead_of_looping_forever(self):
        # 이전 구현은 `shift 2` 가 실패해도 set -e 가 없어 인자가 남았고,
        # while 루프가 영원히 돌았다. 평가 스크립트가 끝나지 않는다.
        for flag in ("--model", "--prompt", "--endpoint"):
            with self.subTest(flag=flag):
                try:
                    result = self._run(flag)
                except subprocess.TimeoutExpired:
                    self.fail(f"{flag} 값 누락 시 종료하지 않는다 (무한 루프)")
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("값이 필요하다", result.stderr)

    def test_unknown_interpreter_names_what_is_missing(self):
        env = dict(os.environ, PYTHON_BIN="python-that-does-not-exist")
        result = subprocess.run(
            ["bash", str(NLU_DIR / "run_nlu.sh"), "--help"],
            capture_output=True, text=True, timeout=15, env=env,
        )
        self.assertEqual(result.returncode, 127)
        self.assertIn("python-that-does-not-exist", result.stderr)

    def test_an_argument_error_is_not_masked_by_the_environment(self):
        # 인터프리터를 먼저 해석하면 인자 오류가 환경 오류로 보고된다.
        env = dict(os.environ, PYTHON_BIN="python-that-does-not-exist")
        result = subprocess.run(
            ["bash", str(NLU_DIR / "run_nlu.sh"), "--model"],
            capture_output=True, text=True, timeout=15, env=env,
        )
        self.assertEqual(result.returncode, 2, result.stderr)

    def test_it_runs_where_bare_python_does_not_exist(self):
        # `python` 이 없는 환경이 실재한다(이 개발 머신). 형제 트랙과 같은 이름을
        # 우선하되, 없으면 python3 으로 간다.
        result = subprocess.run(
            ["bash", str(NLU_DIR / "run_nlu.sh"), "--help"],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--overwrite", result.stdout)


class PathResolution(unittest.TestCase):
    def test_existing_directory_spelling_wins_over_the_normalized_one(self):
        # macOS 는 대소문자를 무시해 이 결함을 숨긴다. 리눅스에서는 한 런의
        # 산출물이 두 디렉토리로 갈린다.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "results" / "google_gemma_4_26B_A4B_it").mkdir(parents=True)
            self.assertEqual(
                runner.results_model_dir_name(base, "google/gemma-4-26B-A4B-it"),
                "google_gemma_4_26B_A4B_it",
            )
            self.assertEqual(
                runner.results_model_dir_name(base, "google/gemma-4-26b-a4b-it"),
                "google_gemma_4_26B_A4B_it",
            )

    def test_ambiguous_casing_is_refused_rather_than_guessed(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "results" / "m_a").mkdir(parents=True)
            try:
                (base / "results" / "M_A").mkdir()
            except FileExistsError:
                # 대소문자를 구분하지 않는 파일시스템(macOS 기본)에서는 이 상태를
                # 만들 수조차 없다 — 그것이 이 결함이 리눅스에서만 드러나는 이유다.
                self.skipTest("case-insensitive filesystem")
            with self.assertRaises(ValueError):
                runner.results_model_dir_name(base, "m/a")

    def test_prompt_file_is_recorded_without_the_host_home_directory(self):
        # 커밋된 산출물에 /home/rainis/... 가 박혀 있어, 내용이 같은 결과가
        # 경로 차이만으로 서로 다른 파일이 되었다.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            target = base / "shared" / "nlu" / "prompt" / "carwash.yaml"
            target.parent.mkdir(parents=True)
            target.write_text("x", encoding="utf-8")
            self.assertEqual(
                runner.repo_relative(base, target),
                str(Path("shared/nlu/prompt/carwash.yaml")),
            )


class OverwriteDefence(unittest.TestCase):
    def test_a_different_requested_model_in_the_same_directory_is_refused(self):
        # safe_model_name 은 '/', '-', ':' 를 모두 '_' 로 보낸다 — a/b, a-b, a:b 가
        # 한 디렉토리를 가리킨다. 매핑은 바꿀 수 없으므로(기존 results/ 트리 전체가
        # 그 표기다) 조용한 덮어쓰기를 실패로 바꾼다.
        self.assertEqual(runner.safe_model_name("a/b"), runner.safe_model_name("a-b"))
        manifest = {"requested_model": "a/b", "endpoint": "http://x/v1"}
        with self.assertRaises(SystemExit):
            runner.check_no_clobber(manifest, "a-b", "http://x/v1")

    def test_the_same_model_on_a_different_endpoint_is_refused(self):
        manifest = {"requested_model": "a/b", "endpoint": "http://x/v1"}
        with self.assertRaises(SystemExit):
            runner.check_no_clobber(manifest, "a/b", "http://y/v1")

    def test_the_same_identity_is_allowed(self):
        manifest = {"requested_model": "a/b", "endpoint": "http://x/v1"}
        runner.check_no_clobber(manifest, "a/b", "http://x/v1")

    def test_an_unreadable_manifest_is_not_treated_as_absent(self):
        # '없음' 으로 취급하면 덮어쓰기 방어가 통째로 사라진다.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            path.write_text("{ 깨진", encoding="utf-8")
            with self.assertRaises(SystemExit):
                runner.load_manifest(path)


class AtomicWrite(unittest.TestCase):
    def test_a_failed_write_leaves_no_truncated_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.json"
            with self.assertRaises(TypeError):
                runner.write_json_atomic(path, {"bad": object()})
            self.assertFalse(path.exists(), "깨진 JSON 이 최종 경로에 남았다")


class ManifestLifecycle(unittest.TestCase):
    """부분 실행이 완결된 런과 구분되어야 한다."""

    def _main(self, base, responses, extra_argv=()):
        argv = ["nlu-gpustack.py", "--model", "m/x", "--endpoint", "http://e/v1", *extra_argv]
        calls = iter(responses)

        def fake(prompt, model, endpoint, timeout=600.0, request_snapshot=None):
            if request_snapshot is not None:
                request_snapshot.update({"model": model, "temperature": 0.0})
            outcome = next(calls)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome, {"model": "m/x@rev1", "id": "resp-1"}

        with mock.patch.object(runner, "get_base_dir", return_value=base), \
             mock.patch.object(runner, "get_timestamp", return_value="20260101_000000"), \
             mock.patch.object(runner, "get_response", side_effect=fake), \
             mock.patch.object(sys, "argv", argv), \
             mock.patch("builtins.print"):
            runner.main()

    def _manifest(self, base):
        path = base / "results" / "m_x" / "20260101_000000" / "language" / "nlu" / "run.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def _prompts(self, base):
        prompt_dir = base / "prompts"
        prompt_dir.mkdir(parents=True, exist_ok=True)
        for name in ("carwash", "jjajangmyeon"):
            (prompt_dir / f"{name}.yaml").write_text(f"{name} 본문", encoding="utf-8")
        return sorted(prompt_dir.glob("*.yaml"))

    def test_a_completed_run_says_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            with mock.patch.object(runner, "PROMPT_DIR", self._prompts(base)[0].parent):
                self._main(base, ["답1", "답2"])
            manifest = self._manifest(base)
            self.assertEqual(manifest["status"], "complete")
            self.assertEqual(sorted(manifest["completed_prompts"]), ["carwash", "jjajangmyeon"])

    def test_a_half_finished_run_is_marked_partial_and_still_fails(self):
        # 이것이 이 트랙의 핵심 결함이었다. 프롬프트 1 성공 / 2 실패면 파일이 하나
        # 남는데, 매니페스트가 없으면 '프롬프트 한 개짜리 정상 런' 과 구분되지 않는다.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            with mock.patch.object(runner, "PROMPT_DIR", self._prompts(base)[0].parent):
                with self.assertRaises(RuntimeError):
                    self._main(base, ["답1", RuntimeError("504")])
            manifest = self._manifest(base)
            self.assertEqual(manifest["status"], "partial")
            self.assertEqual(manifest["completed_prompts"], ["carwash"])
            self.assertIn("504", manifest["failure"])

    def test_a_rerun_resumes_instead_of_destroying_earlier_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            prompt_dir = self._prompts(base)[0].parent
            with mock.patch.object(runner, "PROMPT_DIR", prompt_dir):
                with self.assertRaises(RuntimeError):
                    self._main(base, ["답1", RuntimeError("504")])
                # 두 번째 호출만 남아야 한다 — 첫 프롬프트를 다시 부르면
                # 성공했던 산출물을 말없이 갈아엎는 것이다.
                self._main(base, ["답2"])
            manifest = self._manifest(base)
            self.assertEqual(manifest["status"], "complete")
            run_dir = base / "results" / "m_x" / "20260101_000000" / "language" / "nlu"
            self.assertEqual(
                json.loads((run_dir / "carwash.json").read_text(encoding="utf-8"))["response"],
                "답1",
            )

    def test_a_deleted_artifact_is_re_run_not_declared_complete(self):
        # 매니페스트의 완료 표시를 그대로 믿으면, 산출물이 지워진 뒤에도 complete
        # 로 남는다. 채점기는 그것을 "모델이 형식을 지키지 않았다"로 집계한다 —
        # 없는 파일이 모델의 오답으로 둔갑한다.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            with mock.patch.object(runner, "PROMPT_DIR", self._prompts(base)[0].parent):
                self._main(base, ["답1", "답2"])
                run_dir = base / "results" / "m_x" / "20260101_000000" / "language" / "nlu"
                (run_dir / "carwash.json").unlink()
                self._main(base, ["답1-재실행"])
            self.assertTrue((run_dir / "carwash.json").exists(), "지워진 산출물을 다시 만들어야 한다")
            self.assertEqual(
                json.loads((run_dir / "carwash.json").read_text(encoding="utf-8"))["response"],
                "답1-재실행",
            )
            self.assertEqual(self._manifest(base)["status"], "complete")

    def test_provenance_is_recorded_per_item(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            with mock.patch.object(runner, "PROMPT_DIR", self._prompts(base)[0].parent):
                self._main(base, ["답1", "답2"])
            run_dir = base / "results" / "m_x" / "20260101_000000" / "language" / "nlu"
            record = json.loads((run_dir / "carwash.json").read_text(encoding="utf-8"))
            # 요청한 이름이 아니라 엔드포인트가 서빙했다고 말한 것.
            self.assertEqual(record["served_identity"]["model"], "m/x@rev1")
            self.assertEqual(record["endpoint"], "http://e/v1")
            self.assertIn("prompt_sha256", record)
            # 제약 적용 후의 실제 요청값.
            self.assertEqual(record["request"]["temperature"], 0.0)


if __name__ == "__main__":
    unittest.main()
