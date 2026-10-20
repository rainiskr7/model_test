"""9-1c real CLI bytes captured before extraction, from temporary results only."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from reports import report_taubench_tracks as report


REPO = Path(__file__).resolve().parents[3]


def _write_results(base):
    run = base / "results/model/session/language/taubench"
    run.mkdir(parents=True)
    (run / "summary.json").write_text(json.dumps({
        "benchmark": "tau2", "scoring_version": "synthetic", "model": "model",
        "split": {"domain": "telecom", "name": "test", "task_count": 1,
                  "runnable_task_count": 1, "task_ids": ["t1"]},
        "harness_integrity": {"mode": "standard", "user_implementation": "user_simulator"},
        "by_domain": {"telecom": {"status": "measured", "pass_rate": 0.5,
                                  "passed": 1, "measured": 2,
                                  "task_results": [{"task_id": "t1", "passed": True}]}},
        "publish_status": {"publishable": False, "failures": ["합성 거부", "부분 실행"]},
    }, ensure_ascii=False), encoding="utf-8")
    broken = base / "results/broken/session/language/taubench"
    broken.mkdir(parents=True)
    (broken / "summary.json").write_bytes(b"{")


def _run_cli(base, *args):
    return subprocess.run(
        [sys.executable, "-m", "reports.report_taubench_tracks", "--base", ".", *args],
        cwd=base, env=dict(os.environ, PYTHONPATH=str(REPO), MODEL_TEST_BASE=str(base)),
        capture_output=True, check=False,
    )


def test_empty_cli_returns_two_without_creating_markdown(tmp_path):
    result = _run_cli(tmp_path, "--write-markdown", "report.md", "--strict")
    assert (result.returncode, result.stdout, result.stderr) == (
        2, b"", "taubench 산출물이 없습니다.\n".encode("utf-8"),
    )
    assert not (tmp_path / "report.md").exists()


@pytest.mark.parametrize("write_markdown", [False, True])
@pytest.mark.parametrize("strict", [False, True])
def test_real_cli_markdown_stdout_and_strict_diagnostics(tmp_path, write_markdown, strict):
    _write_results(tmp_path)
    args = [*(["--write-markdown", "report.md"] if write_markdown else []),
            *(["--strict"] if strict else [])]
    result = _run_cli(tmp_path, *args)
    assert (result.returncode, result.stdout, result.stderr) == (
        1 if strict else 0, b"wrote report.md\n" if write_markdown else BODY_STDOUT,
        STRICT_STDERR if strict else b"",
    )
    if write_markdown:
        assert (tmp_path / "report.md").read_bytes() == MARKDOWN
    else:
        assert not (tmp_path / "report.md").exists()


def test_markdown_write_failure_precedes_stdout_and_strict_diagnostics(tmp_path, monkeypatch, capsys):
    _write_results(tmp_path)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError):
        report.main(["--base", ".", "--write-markdown", "absent/report.md", "--strict"])
    assert capsys.readouterr() == ("", "")


def test_extracted_strict_status_matches_original_diagnostic_bytes(tmp_path, monkeypatch, capsys):
    _write_results(tmp_path)
    monkeypatch.chdir(tmp_path)
    summaries, unreadable = report.collect(Path("."))
    assert report._strict_status(summaries, unreadable) == 1
    captured = capsys.readouterr()
    assert (captured.out, captured.err.encode("utf-8")) == ("", STRICT_STDERR)


def test_strict_status_only_rejects_literal_false(capsys):
    summaries = [{}, *({"publish_status": {"publishable": value}} for value in (True, None, 0))]
    assert report._strict_status(summaries, []) == 0
    assert capsys.readouterr() == ("", "")


def test_main_reaches_collect_and_render_module_patches(tmp_path, monkeypatch, capsys):
    _write_results(tmp_path)
    monkeypatch.chdir(tmp_path)
    original_collect = report.collect
    calls = []

    def collect(base):
        calls.append(("collect", base))
        return original_collect(base)

    def render(summaries, unreadable):
        calls.append(("render", len(summaries), len(unreadable)))
        return "patched markdown\n"

    monkeypatch.setattr(report, "collect", collect)
    monkeypatch.setattr(report, "render_markdown", render)
    assert report.main(["--base", ".", "--write-markdown", "report.md", "--strict"]) == 1
    assert calls == [("collect", Path(".")), ("render", 1, 1)]
    assert Path("report.md").read_bytes() == b"patched markdown\n"
    captured = capsys.readouterr()
    assert (captured.out, captured.err.encode("utf-8")) == ("wrote report.md\n", STRICT_STDERR)


# Literal UTF-8 output captured from the unmodified CLI; no path normalization.
BODY_STDOUT = (
    '# taubench 트랙 결과\n'
    '\n'
    '이 파일은 `reports/report_taubench_tracks.py` 가 `summary.json` 에서 생성한다. 손으로 고치지 말 것.\n'
    '\n'
    '읽는 법:\n'
    '\n'
    '- **도메인을 가로질러 평균하지 않는다.** 상류 Overall 은 retail/airline/telecom 을\n'
    '  `base` split 전 과제로 재야 성립한다. 여기 수치는 `test` split 이고 retail 은 부분집합이다.\n'
    '- 점수는 `Pass^1` 을 100점 척도로 적은 것이다. 괄호는 통과/측정 건수다.\n'
    '- 부분집합은 도메인 이름을 달지 않는다 (`retail/test/judge-free-29`).\n'
    '- 사용자 시뮬레이터 프로토콜이 고정되지 않은 런은 모델 간 표에 넣지 않는다.\n'
    '\n'
    '## 비교 코호트\n'
    '\n'
    '### telecom/test — protocol `247edc2852dd5e1d`\n'
    '\n'
    '사용자 시뮬레이터: `None` · mode `standard` · tau2 `None`\n'
    '\n'
    '> **모델 간 비교 불가 (UNCOMPARABLE).** 아래는 개별 런의 관측값이며 서로 나란히 읽으면 안 된다.\n'
    '\n'
    '| 모델 | 축 | Pass^1 | 비교 제외 사유 |\n'
    '|---|---|---:|---|\n'
    '| model | telecom/test | 발행 불가 | 게이트 거부, 사용자 프로토콜 미고정 |\n'
    '\n'
    '## 재현성\n'
    '\n'
    '- `model` · protocol `247edc2852dd5e1d` — **UNVERIFIED**\n'
    '  - 런 1개: `session`\n'
    '  - 이 규약으로 이 모델을 한 번만 돌렸다 — 비교 대상이 없다\n'
    '\n'
    '## 클레임 등급\n'
    '\n'
    '**1회 실행 숫자는 순위표에 올리지 않는다.** 저장·표시·역사 인용은 되지만 우열 주장의 근거는 아니다. 반복 3회 이상이어야 반복성을 관측했다고 말한다.\n'
    '\n'
    '- `model` · protocol `247edc2852dd5e1d` — `snapshot` (k=1) · 반복 1회 — 반복성을 관측하려면 3회가 필요하다\n'
    '\n'
    '### 발행 가능한 우열 주장\n'
    '\n'
    '- 반복 관측된 코호트가 2개 미만이라 비교할 대상이 없다.\n'
    '\n'
    "> 가설검정이 아니다. 신뢰구간도 p-value 도 아니다. **관측된 불안정으로 설명이 끝나는 우열 주장을 거절하는 규칙**일 뿐이며, 거절되지 않았다고 '유의하다'는 뜻이 아니고 거절됐다고 '두 모델이 같다'는 뜻도 아니다.\n"
    '\n'
    '## 읽을 수 없는 산출물\n'
    '\n'
    '- `results/broken/session/language/taubench/summary.json` — JSONDecodeError: Expecting property name enclosed in double quotes: line 1 column 2 (char 1)\n'
    '\n'
).encode("utf-8")

STRICT_STDERR = (
    '[taubench/report] REJECTED: model / session — 합성 거부; 부분 실행\n'
    '[taubench/report] UNREADABLE: results/broken/session/language/taubench/summary.json — JSONDecodeError: Expecting property name enclosed in double quotes: line 1 column 2 (char 1)\n'
    '[taubench/report] NOT CLEAN: 거부 1건, 읽기 실패 1건\n'
).encode("utf-8")

MARKDOWN = (
    '# taubench 트랙 결과\n'
    '\n'
    '이 파일은 `reports/report_taubench_tracks.py` 가 `summary.json` 에서 생성한다. 손으로 고치지 말 것.\n'
    '\n'
    '읽는 법:\n'
    '\n'
    '- **도메인을 가로질러 평균하지 않는다.** 상류 Overall 은 retail/airline/telecom 을\n'
    '  `base` split 전 과제로 재야 성립한다. 여기 수치는 `test` split 이고 retail 은 부분집합이다.\n'
    '- 점수는 `Pass^1` 을 100점 척도로 적은 것이다. 괄호는 통과/측정 건수다.\n'
    '- 부분집합은 도메인 이름을 달지 않는다 (`retail/test/judge-free-29`).\n'
    '- 사용자 시뮬레이터 프로토콜이 고정되지 않은 런은 모델 간 표에 넣지 않는다.\n'
    '\n'
    '## 비교 코호트\n'
    '\n'
    '### telecom/test — protocol `247edc2852dd5e1d`\n'
    '\n'
    '사용자 시뮬레이터: `None` · mode `standard` · tau2 `None`\n'
    '\n'
    '> **모델 간 비교 불가 (UNCOMPARABLE).** 아래는 개별 런의 관측값이며 서로 나란히 읽으면 안 된다.\n'
    '\n'
    '| 모델 | 축 | Pass^1 | 비교 제외 사유 |\n'
    '|---|---|---:|---|\n'
    '| model | telecom/test | 발행 불가 | 게이트 거부, 사용자 프로토콜 미고정 |\n'
    '\n'
    '## 재현성\n'
    '\n'
    '- `model` · protocol `247edc2852dd5e1d` — **UNVERIFIED**\n'
    '  - 런 1개: `session`\n'
    '  - 이 규약으로 이 모델을 한 번만 돌렸다 — 비교 대상이 없다\n'
    '\n'
    '## 클레임 등급\n'
    '\n'
    '**1회 실행 숫자는 순위표에 올리지 않는다.** 저장·표시·역사 인용은 되지만 우열 주장의 근거는 아니다. 반복 3회 이상이어야 반복성을 관측했다고 말한다.\n'
    '\n'
    '- `model` · protocol `247edc2852dd5e1d` — `snapshot` (k=1) · 반복 1회 — 반복성을 관측하려면 3회가 필요하다\n'
    '\n'
    '### 발행 가능한 우열 주장\n'
    '\n'
    '- 반복 관측된 코호트가 2개 미만이라 비교할 대상이 없다.\n'
    '\n'
    "> 가설검정이 아니다. 신뢰구간도 p-value 도 아니다. **관측된 불안정으로 설명이 끝나는 우열 주장을 거절하는 규칙**일 뿐이며, 거절되지 않았다고 '유의하다'는 뜻이 아니고 거절됐다고 '두 모델이 같다'는 뜻도 아니다.\n"
    '\n'
    '## 읽을 수 없는 산출물\n'
    '\n'
    '- `results/broken/session/language/taubench/summary.json` — JSONDecodeError: Expecting property name enclosed in double quotes: line 1 column 2 (char 1)\n'
).encode("utf-8")

