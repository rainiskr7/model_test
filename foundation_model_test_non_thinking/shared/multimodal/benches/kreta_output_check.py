"""Check that a KRETA output directory holds the files the upstream evaluator expects.

Usage: kreta_output_check.py <out_dir>
Must run with cwd = the KRETA repo (data/KRETA), where ``evaluate.py`` lives, exactly
as the shell did before this was extracted from run_kreta.sh / run_kreta_resume.sh.
"""

import sys


def main(argv: list[str]) -> int:
    # 예외: KRETA/eval cwd의 upstream evaluate를 가져온다.
    sys.path.insert(0, ".")
    import evaluate  # noqa: PLC0415 — upstream module, resolvable only from the KRETA cwd

    evaluate.check_files(argv[0])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
