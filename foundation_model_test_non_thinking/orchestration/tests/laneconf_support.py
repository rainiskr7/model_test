"""Disposable checkout for CA1/CA2/CA3; no production credentials or runtime IO."""
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

REPO = Path(__file__).resolve().parents[2]
# HEAD at the start of bundle A. Pin the oracle so later commits retain CA1's regression.
BASELINE_REVISION = "4e4354e122844ba8423c906057064dae6fd3074c"
TRACKS = ("kmmlu", "taubench_std4", "full")
SAMPLE = ("CONFIG=qwen_qwen3.5_27b_fp8\nHOST_ENV=FIXTURE_HOST\n"
          "HOST_DEFAULT=first\nKEYVAR=FIXTURE_KEY\nDISPLAY=fixture\n"
          "SESSION_KMMLU=fixture\nLANE_TOKENIZER=unused\n")


def head_bytes(relative):
    """Read the original HEAD with Git's checkout-relative path syntax."""
    return subprocess.run(["git", "show", f"{BASELINE_REVISION}:./{relative}"],
                          cwd=REPO, check=True, capture_output=True).stdout


class Comparison:
    def __init__(self, base):
        self.base = base.resolve()
        self.orch = self.base / "orchestration"
        for directory in (".venv/bin", "bin", "orchestration/lanes", "orchestration/models",
                          "orchestration/tests"):
            (self.base / directory).mkdir(parents=True, exist_ok=True)
        self.put(".venv/bin/python", "#!/bin/bash\nexec " + shlex.quote(sys.executable) + ' "$@"\n', True)
        self.put(".venv/bin/activate", "export PATH=" + shlex.quote(str(self.base / "bin") +
                                                                 ":/usr/bin:/bin") + "\n")
        self.put("bin/python", '#!/bin/bash\nprintf "%s\\n" "$2" >> ' +
                 shlex.quote(str(self.base / "loader_inputs")) + "\nexec " +
                 shlex.quote(sys.executable) + ' -B "$@"\n', True)
        (self.base / "configs").symlink_to(REPO / "configs", target_is_directory=True)
        self.put(".env", "FIXTURE_KEY=synthetic\nOPENAI_API_KEY=synthetic\nOPENAI_API_KEY_7=synthetic\n")
        for track in TRACKS:
            (self.orch / "lanes" / (track + ".sh")).symlink_to("../run_lane.sh")
        shutil.copyfile(Path(__file__).with_name("laneconf_probe.py"),
                        self.orch / "tests/laneconf_probe.py")
        self.env = dict(PATH="/usr/bin:/bin", HOME=str(self.base), LC_ALL="C",
                        PYTHONPATH=str(self.base), PYTHONDONTWRITEBYTECODE="1")
        self.install("working")

    def put(self, relative, text, executable=False):
        path = self.base / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        if executable:
            path.chmod(0o755)
        return path

    def install(self, side):
        paths = [Path("orchestration/run_lane.sh")]
        for package in ("tracks", "smoke"):
            paths.extend(path.relative_to(REPO) for path in (REPO / "orchestration" / package).iterdir()
                         if path.suffix in (".py", ".sh"))
        for relative in paths:
            target = self.base / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(head_bytes(relative) if side == "HEAD" else (REPO / relative).read_bytes())
        package = self.orch / "laneconf"
        if package.exists():
            shutil.rmtree(package)
        if side != "HEAD":
            # The source tree may hold bytecode from the pytest process itself; copy sources only.
            shutil.copytree(REPO / "orchestration/laneconf", package,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    def run(self, argv, extra=None):
        return subprocess.run(argv, cwd=self.base.parent, env={**self.env, **(extra or {})},
                              capture_output=True, timeout=30)

    def lane(self, model, track="kmmlu", extra=None):
        return self.run(["/bin/bash", str(self.orch / "lanes" / (track + ".sh")), model],
                        {"LANE_DRY_RUN": "1", **(extra or {})})

    def python(self, *args, extra=None):
        return self.run([str(self.base / ".venv/bin/python"), "-B", *args], extra)

    def cli(self, model, track="kmmlu"):
        return self.python("-m", "orchestration.laneconf", "--tracks-dir", str(self.orch / "tracks"),
                           str(self.orch / "models" / (model + ".conf")), track)

    def context(self, model, extra=None):
        return self.python("-m", "orchestration.tests.laneconf_probe", str(self.base), model, extra=extra)

    def evidence(self, name, result):
        directory = self.base / "evidence" / name
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "stdout").write_bytes(result.stdout)
        (directory / "stderr").write_bytes(result.stderr)
        (directory / "rc").write_text(str(result.returncode) + "\n")

    def assert_dry(self):
        for name in ("logs", "results", "preflights", "__pycache__"):
            assert not (self.base / name).exists()
        assert not list(self.orch.rglob("__pycache__"))


def assignments(result):
    """Decode CLI assignments without executing them in the test driver."""
    assert result.returncode == 0, result.stderr
    assert result.stderr == b""
    return dict(shlex.split(line)[0].split("=", 1) for line in result.stdout.decode().splitlines())


def host_line(result):
    assert result.returncode == 0, result.stderr
    return next(line[5:] for line in result.stdout.decode().splitlines() if line.startswith("HOST="))
