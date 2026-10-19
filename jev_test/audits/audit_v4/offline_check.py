"""수용 명령을 네트워크 차단·보호 해시 검증 아래 실행한다. -m 또는 Python script만 허용."""

import argparse
from pathlib import Path
import runpy
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from audits.audit_v4.offline import guard
from audits.audit_v4.preservation import snapshot, verify, inventory, verify_outputs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("Python script or -m module required")
    root = Path(args.root).resolve()
    before, names, status = snapshot(root), inventory(root), 0
    try:
        with guard():
            if command[0] == "-m":
                sys.argv = command[1:]
                runpy.run_module(command[1], run_name="__main__")
            else:
                path = (root / command[0]).resolve()
                if not path.is_relative_to(root):
                    raise ValueError("script outside root")
                sys.argv = [str(path), *command[1:]]
                runpy.run_path(str(path), run_name="__main__")
    except SystemExit as exc:
        status = exc.code or 0
    finally:
        verify(before, snapshot(root))
        verify_outputs(names, inventory(root))
    print('{"offline_boundary":"verified","real_model_calls":0}')
    return status


if __name__ == "__main__":
    raise SystemExit(main())
