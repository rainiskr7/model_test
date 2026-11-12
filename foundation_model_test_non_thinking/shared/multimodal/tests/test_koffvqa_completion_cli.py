"""C7.1: real CLI with a fake client and saved artifacts in a disposable checkout.

KOFFVQA_COMPLETE_REVISION=3b5377e runs test_c71 with the same assertion (must fail).
"""

import json
import shutil

import pytest
from openpyxl import load_workbook

from shared.multimodal.tests.koffvqa_completion_support import Fixture, selected_revision


@pytest.mark.parametrize("profile", ["", "original"])
def test_c71_partial_judge_saves_artifacts_but_fails(tmp_path, profile):
    fx = Fixture(tmp_path / "checkout", selected_revision())
    result = fx.judge(JUDGE_OUTCOME="original_partial" if profile else "partial", extra_args=["--judge-prompt-profile", profile] if profile else [])
    rows = json.loads((fx.judge_dir() / "results.json").read_text())
    summary = json.loads((fx.judge_dir() / "summary.json").read_text())
    assert (summary["total"], summary["scored"], summary["avg_score"]) == (2, 1, 8)
    assert len(rows) == 2 and rows[1]["error"] and rows[1]["score"] is None
    assert result.returncode == 10
    assert result.stderr == "[koffvqa_judge] incomplete: scored 1/2, rows=2\n"
    if profile:
        assert rows[1]["reason"] == rows[1]["raw_judge_output"] == "근거만"
        from shared.multimodal.publish.adapters_koffvqa import adapt_koffvqa_judge
        rejected = adapt_koffvqa_judge(fx.judge_dir())
        assert not rejected["publishable"] and rejected["status"] == "REJECTED"
        assert "judge 오류가 포함됨" in rejected["failures"]


@pytest.mark.parametrize("count,rc", [(0, 10), (2, 0)])
@pytest.mark.parametrize("profile,purpose", [("", ""), ("original", ""), ("original", "migration")])
def test_judge_cli_empty_and_complete(tmp_path, count, rc, profile, purpose):
    fx = Fixture(tmp_path / "checkout")
    result = fx.judge(count=count, extra_args=["--judge-prompt-profile", profile, "--rejudge-purpose", purpose],
                      JUDGE_OUTCOME="original" if profile else "complete")
    assert result.returncode == rc
    assert (fx.judge_dir() / "results.json").is_file()
    assert (fx.judge_dir() / "summary.json").is_file()
    summary = json.loads((fx.judge_dir() / "summary.json").read_text())
    assert ("rejudge_purpose" in summary) is bool(purpose)
    if profile:
        assert summary["judge_prompt_profile"] == "original"
        assert summary["judge_prompt_version"] == "koffvqa-original-v1"
        assert summary["judge_prompt_template_sha256"] == "sha256:812c0c23a231e471163a42f7bf6aeb6b68ba52e6a491f4579e0c45d5712c18f2"
        assert summary["run_config"]["judge"]["prompt_profile"] == "original"
        assert summary["run_config"]["judge"]["prompt_template_sha256"] == summary["judge_prompt_template_sha256"]
    before = {p.name: p.read_bytes() for p in fx.judge_dir().iterdir()}
    for flags in (["--judge-prompt-profile", "" if profile else "original", "--rejudge-purpose", purpose],
                  ["--judge-prompt-profile", profile, "--rejudge-purpose", "" if purpose else "migration"]):
        assert fx.judge(extra_args=flags).returncode == 2
        assert before == {p.name: p.read_bytes() for p in fx.judge_dir().iterdir()}


@pytest.mark.parametrize("revision", ["3b5377e", "6e66cfa"])
def test_complete_judge_preserves_head_artifact_bytes(tmp_path, revision):
    old = Fixture(tmp_path / "old", revision)
    new = Fixture(tmp_path / "new")
    assert old.judge(REQUEST_CAPTURE=str(old.base / "requests.jsonl")).returncode == 0
    pred = "results/fixture_model/fixture_r1/vision/multimodal/koffvqa/model_gen.xlsx"
    (new.base / pred).parent.mkdir(parents=True)
    shutil.copyfile(old.base / pred, new.base / pred)
    assert new.judge(REQUEST_CAPTURE=str(new.base / "requests.jsonl")).returncode == 0
    assert (old.base / "requests.jsonl").read_bytes() == (new.base / "requests.jsonl").read_bytes()
    for name in ("results.json", "summary.json"):
        before = (old.judge_dir() / name).read_text().replace(str(old.base), "<BASE>")
        after = (new.judge_dir() / name).read_text().replace(str(new.base), "<BASE>")
        if name == "summary.json" and revision == "3b5377e":
            summary = json.loads(after)
            assert summary.pop("judge_request") == {
                "model": "fixture-judge", "provider": None, "reasoning_effort": None,
                "max_tokens_requested": None, "max_tokens_effective": 1024, "temperature": 0.0, "seed": 0,
            }
            after = json.dumps(summary, ensure_ascii=False, indent=2)
        assert after == before


def test_invalid_key_and_columns_keep_existing_cli_codes(tmp_path):
    fx = Fixture(tmp_path / "checkout")
    assert fx.judge(FIXTURE_KEY="").returncode == 2
    assert not fx.judge_dir().exists()
    pred = fx.judge_dir().parent / "koffvqa/model_gen.xlsx"
    book = load_workbook(pred)
    book.active["C1"] = "missing_criteria"
    book.save(pred)
    book.close()
    assert fx.judge().returncode == 1
    assert not fx.judge_dir().exists()
