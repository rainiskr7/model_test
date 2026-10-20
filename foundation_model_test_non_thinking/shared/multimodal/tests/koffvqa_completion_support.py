"""Disposable C7 checkout; revision selection changes sources, never assertions."""

import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

from shared.multimodal.tests.koffvqa_fixture_driver import workbook

ROOT = Path(__file__).resolve().parents[3]
JUDGE = "shared/multimodal/benches/koffvqa_api_judge.py"
FULL = "orchestration/tracks/full.sh"


def source(path, revision=None):
    if revision:
        return subprocess.run(["git", "show", f"{revision}:./{path}"], cwd=ROOT,
                              capture_output=True, check=True).stdout
    return (ROOT / path).read_bytes()


class Fixture:
    def __init__(self, base, revision=None):
        self.base = base
        base.mkdir(parents=True)
        self.env = dict(PATH=str(base / "bin") + ":/usr/bin:/bin", HOME=str(base),
                        PYTHONPATH=str(base), PYTHONDONTWRITEBYTECODE="1",
                        MODEL_TEST_BASE=str(base), EVAL_TIMESTAMP="fixture_r1")
        for package in ("shared/multimodal/publish", "orchestration/laneconf"):
            shutil.copytree(ROOT / package, base / package,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        for path in ("derive_multimodal_publish.py", "shared/results_dir.sh",
                     "shared/harness/harness_lib.sh", "orchestration/run_lane.sh",
                     "shared/multimodal/benches/koffvqa_judge_complete.py", JUDGE, FULL):
            self.put(path, source(path, revision if path in (JUDGE, FULL) else None))
        self.put("shared/multimodal/benches/common.py",
                 Path(__file__).with_name("koffvqa_fake_common.py").read_bytes())
        self.put("fixture_driver.py", Path(__file__).with_name("koffvqa_fixture_driver.py").read_bytes())
        # Fail before any socket attempt, including accidental dependency network access.
        self.put("sitecustomize.py", b"import socket\n"
                 b"def denied(*args, **kwargs):\n    raise AssertionError('network forbidden')\n"
                 b"socket.socket.connect = denied\nsocket.socket.connect_ex = denied\n")
        py = shlex.quote(sys.executable)
        self.put("bin/python", f'#!/bin/bash\nexec {py} -B -m fixture_driver "$@"\n', True)
        self.put(".venv/bin/python", f'#!/bin/bash\nexec {py} -B "$@"\n', True)
        self.put(".venv/bin/activate", "export PATH=" + shlex.quote(self.env["PATH"]) + "\n")
        self.put("bin/curl", '#!/bin/bash\nwhile [ "$#" -gt 0 ]; do\n'
                 'if [ "$1" = -o ]; then echo \'{"id":"fixture/model"}\' > "$2"; shift; fi\n'
                 'shift\ndone\nprintf 200\n', True)
        self.put(".env", "FIXTURE_KEY=synthetic\nTAUBENCH_USER_API_KEY=synthetic\n")
        self.configure()
        lane = base / "orchestration/lanes/full.sh"
        lane.parent.mkdir(parents=True)
        lane.symlink_to("../run_lane.sh")
        for stage in ("nlu", "functionchat", "taubench", "multimodal"):
            name = "run_all" if stage == "multimodal" else "run_" + stage
            self.put(f"vsm/{stage}/{name}.sh",
                     f'#!/bin/bash\nexec {py} -B -m fixture_driver stage {stage}\n', True)

    def put(self, path, content, executable=False):
        target = self.base / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content.encode() if isinstance(content, str) else content)
        if executable:
            target.chmod(0o755)
        return target

    def configure(self, resume="", reps=1):
        self.put("orchestration/models/fixture.conf",
                 "CONFIG=fixture\nHOST_ENV=FIXTURE_HOST\nHOST_DEFAULT=fixture.invalid:1\n"
                 "KEYVAR=FIXTURE_KEY\nLANE_DISPLAY=fixture\nSESSION_FULL=fixture\n"
                 f"FULL_REPS={reps}\nFULL_RESUME_FROM={resume}\n")

    def run(self, argv, **env):
        return subprocess.run(argv, cwd=self.base, env={**self.env, **env},
                              capture_output=True, text=True, timeout=45)

    def judge(self, count=2, **env):
        pred = self.base / "results/fixture_model/fixture_r1/vision/multimodal/koffvqa/model_gen.xlsx"
        if not pred.exists():
            workbook(pred, count)
        return self.run([sys.executable, "-B", "-m", "shared.multimodal.benches.koffvqa_api_judge",
                         "--predfile", str(pred), "--target-model", "fixture/model",
                         "--judge-model", "fixture-judge", "--judge-base-url", "http://fixture.invalid/v1",
                         "--judge-api-key-env", "FIXTURE_KEY", "--seed", "0"],
                        **{"FIXTURE_KEY": "synthetic", **env})

    def lane(self, **env):
        return self.run(["/bin/bash", str(self.base / "orchestration/lanes/full.sh"), "fixture"], **env)

    def judge_dir(self, rep=1):
        return self.base / f"results/fixture_model/fixture_r{rep}/vision/multimodal/koffvqa_api_judge"


def selected_revision():
    """KOFFVQA_COMPLETE_REVISION=3b5377e runs the same C7 assertions on old sources."""
    return os.environ.get("KOFFVQA_COMPLETE_REVISION") or None
