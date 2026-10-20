"""무엇: 운영 셸의 합성 실행 환경. 입력: tmp_path. 출력: 가짜 Python/curl·기록 파일."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
FAKE_PY = r'''
import json, os, pathlib, subprocess, sys, time
args = sys.argv[1:]
if "ops/watch.py" in args:
    raise SystemExit(0)
tail = args[args.index("-c") + 2:]
if tail[0].endswith(".py"):
    raise SystemExit(subprocess.call([sys.executable, *args]))
path = pathlib.Path(os.environ["CALLS"])
with path.open("a") as f:
    f.write(json.dumps(tail) + "\n")
if os.environ.get("HOLD") == "1":
    time.sleep(60)
count = sum(json.loads(s)[0] == "run" for s in path.read_text().splitlines())
code = int(os.environ.get("FAIL_CODE", "7"))
if tail[0] == os.environ.get("FAIL_COMMAND") or (tail[0] == "run" and count <= int(os.environ.get("FAIL_RUNS", "0"))):
    print(json.dumps({"ok": False}))
    raise SystemExit(code)
print(json.dumps({"ok": True, "n_deferred": int(os.environ.get("DEFERRED", "0"))}))
'''


@pytest.fixture
def sandbox(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    shutil.copytree(ROOT / "ops", root / "ops")
    (root / "jeveval").symlink_to(ROOT / "jeveval", target_is_directory=True)
    (root / "configs/models").mkdir(parents=True)
    for name, kind, scoring in (("model", "systemone", "separate"),
                                ("b1", "b1", "separate"), ("joint", "systemone", "joint")):
        (root / f"configs/models/{name}.yaml").write_text(yaml.safe_dump(
            dict(kind=kind, served_name="synthetic", auth_env="SYNTHETIC_KEY", question_scoring=scoring)))
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    py = bin_dir / "python"
    py.write_text(f"#!{sys.executable}\n" + FAKE_PY)
    py.chmod(0o755)
    curl = bin_dir / "curl"
    curl.write_text('#!/bin/bash\nprintf "%s\\n" "$*" >> "$CURL_CALLS"\n'
                    'case "$*" in *v1/models*) echo \'{"data": [{"id": "synthetic"}]}\' ;; *) echo 200;; esac\n')
    curl.chmod(0o755)
    for name in ("sleep", "dscacheutil"):
        p = bin_dir / name
        p.write_text('#!/bin/bash\nif [ "${OPS_TEST_REAL_SLEEP:-0}" = 1 ] && [ "${0##*/}" = sleep ]; then exec /bin/sleep "$@"; fi\nexit 0\n')
        p.chmod(0o755)
    ps = bin_dir / "ps"
    ps.write_text(f"#!{sys.executable}\n" + '''
import os, sys
pid = int(sys.argv[sys.argv.index("-p") + 1])
try:
    os.kill(pid, 0)
except ProcessLookupError:
    raise SystemExit(1)
print("synthetic-start" if "lstart=" in sys.argv else "S" if "stat=" in sys.argv else "bash ops/lane.sh")
''')
    ps.chmod(0o755)
    calls, curls = tmp_path / "calls", tmp_path / "curls"
    env = {**os.environ, "JEV_PY": str(py), "SYNTHETIC_KEY": "fixture-value",
           "CALLS": str(calls), "CURL_CALLS": str(curls), "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
           "PYTHONDONTWRITEBYTECODE": "1", "SETS": "kmhas"}

    def run(script="lane", args=None, **overrides):
        if args is None:
            args = ["model", "host", "fallback", "1234", "SYNTHETIC_KEY", "r1"]
        return subprocess.run(["bash", f"ops/{script}.sh", *args], cwd=root,
                              env={**env, **overrides}, capture_output=True, text=True, timeout=20)

    return SimpleNamespace(root=root, env=env, run=run, calls=calls, curls=curls,
                           commands=lambda: [json.loads(s) for s in calls.read_text().splitlines()] if calls.exists() else [])
