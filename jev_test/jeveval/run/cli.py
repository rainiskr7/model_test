"""무엇: 실행 CLI · 입력: 하위 명령/인자 · 출력: 원문 없는 JSON 한 줄 · 계약 §5-7·⑥b."""

import argparse
import json
from pathlib import Path

from jeveval.run import cmd_archive, cmd_certify, cmd_compare, cmd_replay, cmd_run, cmd_score, cmd_threshold, cmd_t0


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
    for name in ("threshold", "score", "certify"):
        commands.add_parser(name).add_argument("--run-dir", required=True)
    compare = commands.add_parser("compare")
    compare.add_argument("--run-dirs", nargs="+", required=True)
    compare.add_argument("--compare-id", required=True)
    compare.add_argument("--results", default="results")
    archive = commands.add_parser("archive")
    archive.add_argument("--run-id", required=True)
    archive.add_argument("--results", default="results")
    archive.add_argument("--archive-root", default="archive")
    cmd_t0.configure(commands)
    args = vars(parser.parse_args(argv))
    command = args.pop("command")
    handler = {"run": cmd_run, "threshold": cmd_threshold, "score": cmd_score,
               "certify": cmd_certify, "compare": cmd_compare, "archive": cmd_archive,
               "replay": cmd_replay, "t0": cmd_t0}[command]
    try:
        result = handler.run(root=Path.cwd(), **args)
    except Exception:
        # 로더/전송/외부 인코더의 예외 문자열에는 원문·키가 있을 수 있다.
        result = dict(ok=False, error="command input or execution failed")
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":"), allow_nan=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
