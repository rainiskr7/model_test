"""Reject a stale KRETA resume context (resume run).

Usage: kreta_resume_context_check.py <benches_dir> <run_config.json> <existing .resume_context.json> <setting> <session>
Exit 1 with a message when the stored context cannot be read or differs from the one
the current config would produce. Extracted from run_kreta_resume.sh.
"""

import json
import sys
from pathlib import Path


def check_resume_context(benches_dir: str, config_path: Path, context_path: Path, setting: str, session: str) -> None:
    # 예외: 호출자가 지정한 benches_dir/metadata 인자 계약을 유지한다.
    sys.path.insert(0, benches_dir)
    from metadata import build_resume_context  # noqa: PLC0415 — benches_dir is only known at call time

    config = json.loads(config_path.read_text(encoding="utf-8"))
    expected = build_resume_context(config, setting=setting, session=session)
    try:
        actual = json.loads(context_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"resume context 읽기 실패: {exc}")
    if actual != expected:
        raise SystemExit(f"stale resume context 거부: expected={expected!r}, actual={actual!r}")


def main(argv: list[str]) -> int:
    benches_dir, config, context, setting, session = argv[:5]
    check_resume_context(benches_dir, Path(config), Path(context), setting, session)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
