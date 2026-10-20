"""C7.2: real full lane, judge, derive and completion CLI; all IO stays in tmp_path.

KOFFVQA_COMPLETE_REVISION=3b5377e selects git-show copies of judge/full only.
The two test_c72 assertions must FAIL on rc 0, without changing the assertions.
"""

import json

import pytest

from shared.multimodal.tests.koffvqa_completion_support import Fixture, selected_revision


@pytest.mark.parametrize("resume", [False, True], ids=["fresh", "derive_resume"])
def test_c72_incomplete_lane_never_succeeds(tmp_path, resume):
    fx = Fixture(tmp_path / "checkout", selected_revision())
    if resume:
        fx.judge(count=275, JUDGE_OUTCOME="partial")
    fx.configure("r1:derive" if resume else "", reps=2)
    result = fx.lane(JUDGE_OUTCOME="partial")
    calls = (fx.base / "calls").read_text()
    assert "fixture_r1 derive 0\n" in calls
    assert "fixture_r2 derive 0\n" in calls
    sidecar = json.loads((fx.judge_dir() / "_derived/publish.json").read_text())
    assert sidecar["status"] == "REJECTED" and sidecar["publishable"] is False
    assert sidecar["counts"]["errored"] == 1
    assert result.returncode == 1
    assert "fixture_r1 koffvqa_judge_complete 10\n" in calls
    assert "fixture_r2 koffvqa_judge_complete 0\n" in calls
    if not resume:
        assert "fixture_r1 koffvqa_api_judge 10\n" in calls
        assert "판정 실패 2건" in result.stdout
    else:
        assert "fixture_r1 koffvqa_api_judge" not in calls
        assert "판정 실패 1건" in result.stdout


@pytest.mark.parametrize("count,publishable", [(275, True), (2, False)])
def test_complete_resume_does_not_require_publishability(tmp_path, count, publishable):
    fx = Fixture(tmp_path / "checkout")
    assert fx.judge(count=count).returncode == 0
    fx.configure("r1:derive")
    assert fx.lane().returncode == 0
    sidecar = json.loads((fx.judge_dir() / "_derived/publish.json").read_text())
    assert sidecar["publishable"] is publishable


def test_total_mismatch_fails_even_when_derive_is_publishable(tmp_path):
    fx = Fixture(tmp_path / "checkout")
    assert fx.judge(count=275).returncode == 0
    path = fx.judge_dir() / "summary.json"
    summary = json.loads(path.read_text())
    summary["total"] = 276
    path.write_text(json.dumps(summary))
    fx.configure("r1:derive")
    assert fx.lane().returncode == 1
    assert json.loads((fx.judge_dir() / "_derived/publish.json").read_text())["publishable"] is True


def test_completion_is_checked_after_native_skip(tmp_path):
    fx = Fixture(tmp_path / "checkout")
    assert fx.judge(count=275).returncode == 0
    path = fx.judge_dir() / "summary.json"
    summary = json.loads(path.read_text())
    summary["total"] = 276
    path.write_text(json.dumps(summary))
    # Existing publisher does not check summary.total: bind a valid NATIVE to these bytes.
    result = fx.run([str(fx.base / ".venv/bin/python"), "-B", "derive_multimodal_publish.py",
                     "--base", ".", "--source", str(fx.judge_dir()), "--write", "--native"])
    assert result.returncode == 0
    sidecar = fx.judge_dir() / "_derived/publish.json"
    before = sidecar.read_bytes()
    fx.configure("r1:derive")
    assert fx.lane().returncode == 1
    assert sidecar.read_bytes() == before
    assert "skipped existing NATIVE" in (fx.base / "logs/fixture_r1/derive.log").read_text()


def test_broken_saved_json_remains_a_lane_failure(tmp_path):
    fx = Fixture(tmp_path / "checkout")
    assert fx.judge().returncode == 0
    (fx.judge_dir() / "summary.json").write_text("broken")
    fx.configure("r1:derive")
    assert fx.lane().returncode == 1
    assert "fixture_r1 koffvqa_judge_complete 2\n" in (fx.base / "calls").read_text()


def test_missing_explicit_judge_resume_input_is_error(tmp_path):
    fx = Fixture(tmp_path / "checkout")
    fx.configure("r1:koffvqa_judge", reps=2)
    result = fx.lane()
    assert result.returncode == 2
    assert "koffvqa_judge 재개 불가" in result.stdout
    assert not (fx.base / "calls").exists()


def test_judge_resume_and_later_conditional_skip(tmp_path):
    fx = Fixture(tmp_path / "checkout")
    assert fx.judge().returncode == 0  # supplies the first repetition's workbook
    fx.configure("r1:koffvqa_judge", reps=2)
    fx.put("no_outputs", "")
    result = fx.lane()
    assert result.returncode == 0
    assert "fixture_r1 koffvqa_api_judge 0" in (fx.base / "calls").read_text()
    assert "[fixture_r2] koffvqa_judge skip (condition)" in result.stdout


@pytest.mark.parametrize("rc", [1, 2, 3, 130])
def test_other_judge_failures_never_derive_old_artifacts(tmp_path, rc):
    fx = Fixture(tmp_path / "checkout")
    assert fx.judge().returncode == 0
    fx.configure("r1:koffvqa_judge")
    fx.put("override_koffvqa_api_judge", str(rc))
    assert fx.lane().returncode == (rc if rc in (3, 130) else 1)
    assert " derive " not in (fx.base / "calls").read_text()


@pytest.mark.parametrize("rc", [1, 2, 3, 130])
def test_failed_derive_does_not_run_completion_or_mask_rc(tmp_path, rc):
    fx = Fixture(tmp_path / "checkout")
    assert fx.judge().returncode == 0
    fx.configure("r1:derive")
    fx.put("override_derive", str(rc))
    assert fx.lane().returncode == (rc if rc in (3, 130) else 1)
    assert "koffvqa_judge_complete" not in (fx.base / "calls").read_text()
