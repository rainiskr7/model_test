"""무엇: 운영 설정·JSON 판독. 입력: 하위 명령/파일/표준입력. 출력: 필요한 값만, 오류는 고정 문구."""

import json
import sys
from pathlib import Path

from jeveval.io.config import read_yaml
from jeveval.io.run_files import read_json


def run(args):
    command, *args = args
    if command == "model":
        value = read_yaml(args[0])
        if value["kind"] not in ("systemone", "b1"):
            raise ValueError("kind")
        if value["question_scoring"] not in ("joint", "separate"):
            raise ValueError("question_scoring")
        fields = [value[k] for k in ("kind", "served_name", "auth_env", "question_scoring")]
        if any(not isinstance(v, str) or not v or any(c.isspace() for c in v) for v in fields):
            raise ValueError("model")
        print("\t".join(fields))
    elif command == "env":
        path, key = args
        values = [line.split("=", 1)[1].strip() for line in Path(path).read_text().splitlines()
                  if line.startswith(key + "=")]
        if len(values) != 1:
            raise ValueError("env")
        value = values[0]
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if not value or any(ord(c) < 32 or ord(c) > 126 for c in value):
            raise ValueError("env")
        print(value)
    elif command == "served":
        if args[0] not in {row["id"] for row in json.load(sys.stdin)["data"]}:
            raise ValueError("served")
    elif command == "ping":
        print(json.dumps(dict(model=args[0], messages=[dict(role="user", content="ping")], max_tokens=1)))
    elif command == "deferred":
        value = json.load(sys.stdin)
        count = value["n_deferred"]
        if value.get("ok") is not True or type(count) is not int or count < 0:
            raise ValueError("deferred")
        print(count)
    elif command == "compare":
        path, *models = args
        if Path(path).exists():
            saved = read_json(path)
            if saved.get("schema") != "compare/1" or sorted(saved["models"]) != sorted(models):
                raise ValueError("comparison models differ")
    else:
        raise ValueError("command")


if __name__ == "__main__":
    try:
        run(sys.argv[1:])
    except Exception:
        print("ops input check failed", file=sys.stderr)
        raise SystemExit(2) from None
