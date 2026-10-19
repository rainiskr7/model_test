"""무엇: 실행 CLI · 입력: 하위 명령/인자 · 출력: 원문 없는 JSON 한 줄 · 계약 §5-7·⑥b."""

import argparse
import json
from pathlib import Path

from jeveval.run import cmd_question_threshold, cmd_report, cmd_question_risk, cmd_archive, cmd_certify, cmd_compare, cmd_replay, cmd_run, cmd_score, cmd_threshold, cmd_t0


def _report_commands(commands):
    """보고와 탐색 분석의 인자만 조립한다."""
    report = commands.add_parser("report")
    report.add_argument("--run-id", required=True)
    report.add_argument("--models", nargs="+", required=True)
    report.add_argument("--results", default="results")
    report.add_argument("--compare-id", nargs="+")
    report.add_argument("--note-unrun", nargs="+")
    report.add_argument("--out")
    questions = commands.add_parser("question-risk")
    questions.add_argument("--run-dir", required=True)
    questions.add_argument("--history", action="store_true")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run and certify Jev evaluations")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--model", required=True)
    run.add_argument("--task", required=True)
    run.add_argument("--stage", choices=("dev", "test", "extra"), required=True)
    run.add_argument("--run-id", required=True)
    run.add_argument("--base-url")
    run.add_argument("--results", default="results")
    run.add_argument("--check-config", action="store_true")
    run.add_argument("--offline", action="store_true")
    replay = commands.add_parser("replay")
    for field in ("model", "task", "run-id", "source-run-dir"):
        replay.add_argument("--" + field, required=True)
    replay.add_argument("--stage", choices=("dev", "test", "extra"), required=True)
    replay.add_argument("--results", default="results")
    replay.add_argument("--reason")
    for name in ("threshold", "question-threshold", "score", "certify"):
        commands.add_parser(name).add_argument("--run-dir", required=True)
    compare = commands.add_parser("compare")
    compare.add_argument("--run-dirs", nargs="+", required=True)
    compare.add_argument("--compare-id", required=True)
    compare.add_argument("--results", default="results")
    archive = commands.add_parser("archive")
    archive.add_argument("--run-id", required=True)
    archive.add_argument("--results", default="results")
    archive.add_argument("--archive-root", default="archive")
    _report_commands(commands)
    cmd_t0.configure(commands)
    args = vars(parser.parse_args(argv))
    command = args.pop("command")
    handler = {"run": cmd_run, "threshold": cmd_threshold, "score": cmd_score,
               "certify": cmd_certify, "compare": cmd_compare, "archive": cmd_archive,
               "replay": cmd_replay, "t0": cmd_t0, "report": cmd_report,
               "question-risk": cmd_question_risk, "question-threshold": cmd_question_threshold}[command]
    try:
        result = handler.run(root=Path.cwd(), **args)
    except Exception:
        # 로더/전송/외부 인코더의 예외 문자열에는 원문·키가 있을 수 있다.
        result = dict(ok=False, error="command input or execution failed")
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":"), allow_nan=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
