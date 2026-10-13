"""Write the KRETA resume context atomically (fresh run).

Usage: kreta_resume_context.py <benches_dir> <run_config.json> <out .resume_context.json> <setting> <session>
Extracted from run_kreta.sh; the shell calls it with the same argv as the old heredoc.
"""

import json
import os
import sys
from pathlib import Path


def write_resume_context(benches_dir: str, config_path: Path, out_path: Path, setting: str, session: str) -> None:
    sys.path.insert(0, benches_dir)
    from metadata import build_resume_context  # noqa: PLC0415 — benches_dir is only known at call time

    config = json.loads(config_path.read_text(encoding="utf-8"))
    value = build_resume_context(config, setting=setting, session=session)
    tmp = out_path.with_name(f".{out_path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, out_path)


def main(argv: list[str]) -> int:
    benches_dir, config, out, setting, session = argv[:5]
    write_resume_context(benches_dir, Path(config), Path(out), setting, session)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
