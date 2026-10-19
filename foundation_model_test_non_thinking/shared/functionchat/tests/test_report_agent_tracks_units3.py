"""9-1c real CLI bytes captured before extraction; no output fields are omitted."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from reports import report_agent_tracks as report


REPO = Path(__file__).resolve().parents[3]


def _write_results(base):
    for model, status in (
        ("alpha", {"publishable": True, "failures": []}),
        ("beta", {"publishable": False, "failures": ["합성 거부", "부분 실행"]}),
        ("legacy", None),
    ):
        run = base / "results" / model / "session" / "language/functionchat"
        run.mkdir(parents=True)
        summary = {"model": model, "scoring_version": "synthetic", "overall": {"passed": 1, "measured": 2}}
        if status is not None:
            summary["publish_status"] = status
        (run / "summary.json").write_text(json.dumps(summary, ensure_ascii=False), encoding="utf-8")
        if model == "alpha":
            (run / "judge.json").write_text(json.dumps({
                "judge": {"human_validation": "not performed"},
                "overall": {"passed": 2, "judged": 3, "judge_errors": 1, "unstable": 2},
            }), encoding="utf-8")


def _run_cli(base, *args):
    return subprocess.run(
        [sys.executable, "-m", "reports.report_agent_tracks", "--base", ".", *args],
        cwd=base, env=dict(os.environ, PYTHONPATH=str(REPO), MODEL_TEST_BASE=str(base)),
        capture_output=True, check=False,
    )


def test_empty_cli_returns_two_without_creating_markdown(tmp_path):
    result = _run_cli(tmp_path, "--write-markdown", "report.md", "--strict")
    assert (result.returncode, result.stdout, result.stderr) == (2, b"", "산출물이 없습니다.\n".encode("utf-8"))
    assert not (tmp_path / "report.md").exists()


@pytest.mark.parametrize("strict", [False, True])
def test_real_cli_writes_markdown_then_console_and_preserves_strict_rc(tmp_path, strict):
    _write_results(tmp_path)
    args = ["--write-markdown", "report.md", *(["--strict"] if strict else [])]
    result = _run_cli(tmp_path, *args)
    assert (result.returncode, result.stdout, result.stderr) == (1 if strict else 0, WRITTEN_STDOUT, b"")
    assert (tmp_path / "report.md").read_bytes() == MARKDOWN


def test_real_cli_without_markdown_prints_same_console(tmp_path):
    _write_results(tmp_path)
    result = _run_cli(tmp_path)
    assert (result.returncode, result.stdout, result.stderr) == (0, CONSOLE_STDOUT, b"")
    assert not (tmp_path / "report.md").exists()


def test_markdown_write_failure_precedes_console_output(tmp_path, monkeypatch, capsys):
    _write_results(tmp_path)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError):
        report.main(["--base", ".", "--write-markdown", "absent/report.md"])
    assert capsys.readouterr() == ("", "")


def test_extracted_console_matches_original_cli_bytes(tmp_path, monkeypatch, capsys):
    _write_results(tmp_path)
    monkeypatch.chdir(tmp_path)
    rows = report.collect(Path("."))
    report._print_console(
        [r for r in rows if r["publishable"]], [r for r in rows if not r["publishable"]],
        [r for r in rows if not r["has_gate_record"]], True,
    )
    captured = capsys.readouterr()
    assert (captured.out.encode("utf-8"), captured.err) == (CONSOLE_STDOUT, "")


def test_main_reaches_render_and_fraction_patches_after_writing(tmp_path, monkeypatch, capsys):
    _write_results(tmp_path)
    monkeypatch.chdir(tmp_path)
    calls = []

    def render(rows, repro_report, claims):
        calls.append(("render", len(rows), len(repro_report), len(claims["credentials"])))
        return "patched markdown\n"

    def fraction(num, den):
        assert Path("report.md").read_bytes() == b"patched markdown\n"
        calls.append(("fraction", num, den))
        return "PATCHED"

    monkeypatch.setattr(report, "render_markdown", render)
    monkeypatch.setattr(report, "fraction", fraction)
    assert report.main(["--base", ".", "--write-markdown", "report.md", "--strict"]) == 1
    assert calls == [("render", 3, 3, 3), ("fraction", 1, 2), ("fraction", 2, 3)]
    captured = capsys.readouterr()
    assert captured.out.encode("utf-8") == WRITTEN_STDOUT.replace(b"1/2 = 0.5000", b"PATCHED").replace(
        b"2/3 = 0.6667", b"PATCHED",
    )
    assert captured.err == ""


# Literal UTF-8 output captured from the unmodified CLI; no path normalization.
WRITTEN_STDOUT = (
    '  wrote report.md\n'
    '==============================================================================\n'
    '발행 가능 (publish_status.publishable == true)\n'
    '==============================================================================\n'
    '  [functionchat] alpha / session\n'
    '      exact        1/2 = 0.5000\n'
    '      judged       2/3 = 0.6667  ** PROVISIONAL — 판정기 기준, 인간 검증 없음 **\n'
    '      (판정 불가 1, 불안정 2)\n'
    '\n'
    '==============================================================================\n'
    '발행 불가 — 점수를 인용하지 마십시오\n'
    '==============================================================================\n'
    '  [functionchat] beta / session\n'
    '      X 합성 거부\n'
    '      X 부분 실행\n'
    '  [functionchat] legacy / session\n'
    '      X 게이트 기록 없음 — 현재 채점 계약으로 재채점되지 않는 낡은 산출물\n'
    '\n'
    '  ⚠️  게이트 기록이 없는 런 (재채점하세요):\n'
    '      legacy/session/functionchat\n'
    '\n'
    '  발행 가능 1 / 거부 2 / 게이트 기록 없음 1\n'
    '  상세 판단 기준: AGENT_TRACK_CLOSEOUT.md\n'
).encode("utf-8")

CONSOLE_STDOUT = (
    '==============================================================================\n'
    '발행 가능 (publish_status.publishable == true)\n'
    '==============================================================================\n'
    '  [functionchat] alpha / session\n'
    '      exact        1/2 = 0.5000\n'
    '      judged       2/3 = 0.6667  ** PROVISIONAL — 판정기 기준, 인간 검증 없음 **\n'
    '      (판정 불가 1, 불안정 2)\n'
    '\n'
    '==============================================================================\n'
    '발행 불가 — 점수를 인용하지 마십시오\n'
    '==============================================================================\n'
    '  [functionchat] beta / session\n'
    '      X 합성 거부\n'
    '      X 부분 실행\n'
    '  [functionchat] legacy / session\n'
    '      X 게이트 기록 없음 — 현재 채점 계약으로 재채점되지 않는 낡은 산출물\n'
    '\n'
    '  ⚠️  게이트 기록이 없는 런 (재채점하세요):\n'
    '      legacy/session/functionchat\n'
    '\n'
    '  발행 가능 1 / 거부 2 / 게이트 기록 없음 1\n'
    '  상세 판단 기준: AGENT_TRACK_CLOSEOUT.md\n'
).encode("utf-8")

MARKDOWN = (
    '# agent 트랙 결과\n'
    '\n'
    '이 파일은 `foundation_model_test_non_thinking/reports/report_agent_tracks.py` 가 산출물에서 생성한다. 손으로 고치지 말 것 — 다시 생성하면 덮어써진다.\n'
    '\n'
    '발행 가능한 **런** 1개 / 거부 2개. 아래 표는 축별 대표 런만 보여주므로 행 수는 이보다 적다. 판단 기준은 [`AGENT_TRACK_CLOSEOUT.md`](AGENT_TRACK_CLOSEOUT.md).\n'
    '\n'
    '> taubench 는 이 보고서에 없다. 사용자 시뮬레이터 프로토콜 고정 여부와 공식 split 커버리지를 보는 전용 계층이 판정을 갖는다 — `foundation_model_test_non_thinking/TAUBENCH_TRACK_RESULTS.md` (`report_taubench_tracks.py` 가 생성).\n'
    '\n'
    '## 발행 가능한 수치 (축별 대표 런)\n'
    '\n'
    '| 트랙 | 모델 | 런 | 축 | 결과 | 상태 |\n'
    '|---|---|---|---|---|---|\n'
    '| functionchat | alpha | session | exact | 1/2 = 0.5000 | 확정 |\n'
    '| functionchat | alpha | session | judged | 2/3 = 0.6667 | PROVISIONAL — 판정기 기준, 인간 검증 없음 · 프로비넌스 없음(endpoint, served_identity, rubric_sha256) |\n'
    '\n'
    '## 발행 불가 — 점수를 인용하지 마십시오\n'
    '\n'
    '- **beta / session / functionchat**\n'
    '  - 합성 거부\n'
    '  - 부분 실행\n'
    '- **legacy / session / functionchat**\n'
    '  - 게이트 기록 없음 — 현재 채점 계약으로 재채점되지 않는 낡은 산출물\n'
    '\n'
    '## 재현성 (반복 실행)\n'
    '\n'
    '**건수가 같다고 같은 측정이 아니다.** 통과한 **항목 집합**을 대조한다 — 실측으로 통과 건수가 5런 내내 동일한데 통과 항목이 10개 뒤집힌 사례가 있다.\n'
    '\n'
    '- `alpha` · `synthetic` — **UNVERIFIED**\n'
    '  - 런 1개: `session`\n'
    '  - 이 규약으로 이 모델을 한 번만 돌렸다 — 비교 대상이 없다\n'
    '- `beta` · `synthetic` — **UNVERIFIED**\n'
    '  - 런 1개: `session`\n'
    '  - 이 규약으로 이 모델을 한 번만 돌렸다 — 비교 대상이 없다\n'
    '- `legacy` · `synthetic` — **UNVERIFIED**\n'
    '  - 런 1개: `session`\n'
    '  - 이 규약으로 이 모델을 한 번만 돌렸다 — 비교 대상이 없다\n'
    '\n'
    '## 클레임 등급\n'
    '\n'
    '**1회 실행 숫자는 순위표에 올리지 않는다.** 저장·표시·역사 인용은 되지만 우열 주장의 근거는 아니다. 반복 3회 이상이어야 반복성을 관측했다고 말한다.\n'
    '\n'
    '### exact-match 축\n'
    '\n'
    '- `alpha` (`synthetic`) — `not_measured` (k=1) · 런들이 공통으로 채점한 항목이 없다 — 반복 횟수와 무관하게 이 코호트는 측정된 것이 없다\n'
    '- `beta` (`synthetic`) — `not_measured` (k=1) · 런들이 공통으로 채점한 항목이 없다 — 반복 횟수와 무관하게 이 코호트는 측정된 것이 없다\n'
    '- `legacy` (`synthetic`) — `not_measured` (k=1) · 런들이 공통으로 채점한 항목이 없다 — 반복 횟수와 무관하게 이 코호트는 측정된 것이 없다\n'
    '\n'
    '### judge 축 — 런 내부 3표\n'
    '\n'
    '판정 축은 exact-match 축과 합치지 않는다. 이 예산은 반복 실행 간 뒤집힘이 아니라, 같은 런에서 항목별 3표가 갈린 수로 만든 판정기 내부 불안정이다.\n'
    '\n'
    '- `alpha` / `session` — `repeatability_observed` (런 내부 3표, k=1) · 다수결 0/0 · 표 갈림 0건 · 불안정 예산 0–0 · **PROVISIONAL — 판정기 기준, 인간 검증 없음**\n'
    '\n'
    '### 발행 가능한 우열 주장\n'
    '\n'
    '**exact-match 축**\n'
    '\n'
    '- 반복 관측된 코호트가 2개 미만이라 비교할 대상이 없다.\n'
    '\n'
    "> 가설검정이 아니다. 신뢰구간도 p-value 도 아니다. **관측된 불안정으로 설명이 끝나는 우열 주장을 거절하는 규칙**일 뿐이며, 거절되지 않았다고 '유의하다'는 뜻이 아니고 거절됐다고 '두 모델이 같다'는 뜻도 아니다.\n"
    '\n'
    '## 읽는 법\n'
    '\n'
    '- 분자/분모를 함께 본다. 반올림된 점수만으로는 표본 크기가 사라진다.\n'
    '- **축을 합산하거나 평균하지 않는다.** 서로 다른 능력을 잰다.\n'
    '- PROVISIONAL 은 인간 검증 전이다. 정답률이 아니라 판정기 기준 점수다.\n'
    '- 거부된 런의 숫자는 존재하더라도 인용하지 않는다.\n'
    '- 재현성은 **대표 런과 다른 코호트**일 수 있다. 대표가 `UNVERIFIED` 인데 다른 scoring_version 이 `DIVERGED` 라면, 발행 중인 수치에는 재현 근거가 없다는 뜻이다.\n'
).encode("utf-8")

