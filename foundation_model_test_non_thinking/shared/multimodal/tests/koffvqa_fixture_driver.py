"""Subprocess adapters for C7 fixtures; real judge, derive and completion CLIs."""

import os
from pathlib import Path
import subprocess
import sys

from openpyxl import Workbook


def workbook(path, count=275):
    path.parent.mkdir(parents=True, exist_ok=True)
    book = Workbook()
    book.active.append(["index", "question", "answer", "prediction"])
    for index in range(count):
        book.active.append([str(index), "question", "rubric", "prediction"])
    book.save(path)
    book.close()


def main():
    args = sys.argv[1:]
    base = Path(os.environ["MODEL_TEST_BASE"])
    if args[0].endswith("/configs/load_model_config.py"):
        print("export MODEL=fixture/model\nexport BASE_URL_CHAT=http://fixture.invalid/v1/chat/completions\n"
              "export BASE_URL_V1=http://fixture.invalid/v1")
        return 0
    ts = os.environ["EVAL_TIMESTAMP"]
    if args[0] == "stage":
        stage = args[1]
        if stage == "multimodal" and not (base / "no_outputs").exists():
            workbook(base / "results/fixture_model" / ts / "vision/multimodal/koffvqa/model_gen.xlsx")
        rc = 0
    else:
        stage = "derive" if args[0] == "derive_multimodal_publish.py" else args[1].rsplit(".", 1)[-1]
        override = base / ("override_" + stage)
        rc = int(override.read_text()) if override.exists() else subprocess.run(
            [sys.executable, "-B", *args], cwd=base, check=False,
        ).returncode
    with (base / "calls").open("a") as stream:
        stream.write(f"{ts} {stage} {rc}\n")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
