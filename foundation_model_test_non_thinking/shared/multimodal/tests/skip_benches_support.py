"""Isolated shell driver: no real bench, Python helper, or operational output."""

import os
from pathlib import Path
import subprocess


REPO = Path(__file__).resolve().parents[3]
SCRIPT = "shared/multimodal/run_all.sh"
NAMES = ("kreta", "k_dtcbench", "koffvqa", "mtvqa_kr", "k_mmbench", "b4_latency_profile")
WRAPPERS = (*NAMES, "kreta_resume", "ko_vlm_benchmark", "b3_structured_output")


def source(revision=None):
    """Read the working copy or a requested git revision without checking it out."""
    if revision is None:
        return (REPO / SCRIPT).read_text(encoding="utf-8")
    return subprocess.run(
        ["git", "show", f"{revision}:./{SCRIPT}"], cwd=REPO,
        capture_output=True, text=True, check=True,
    ).stdout


def snapshot(root):
    """Record tree, content and modification times, including empty directories."""
    return {
        path.relative_to(root).as_posix(): (
            path.stat().st_mode, path.stat().st_mtime_ns,
            path.read_bytes() if path.is_file() else None,
        )
        for path in [root, *root.rglob("*")]
    }


class Driver:
    def __init__(self, root, text, *, stop=False):
        self.root = root
        self.script = root / SCRIPT
        self.script.parent.mkdir(parents=True)
        self.script.write_text(text, encoding="utf-8")
        for name in WRAPPERS:
            (self.script.parent / f"run_{name}.sh").write_text(
                f"#!/bin/bash\nprintf 'FAKE_BENCH={name}\\n'\n"
                f'[ "${{FAKE_FAIL:-}}" != "{name}" ] || exit 7\nexit 0\n',
                encoding="utf-8",
            )
        # Deliberately omit the B-3 manifest; the real preflight cannot be invoked.
        fake_py = root / "fake-python"
        fake_py.write_text(
            "#!/bin/bash\nprintf 'FAKE_PY_STOP\\n' >&2\nexit 97\n" if stop else
            '#!/bin/bash\n'
            'if [ "$1" = -c ]; then printf "m\\n"; exit 0; fi\n'
            'if [ "$1" = -m ] && [ "$2" = shared.multimodal.benches.session_sanity ] '
            '&& [ "$3" = "$MODEL_TEST_BASE/results/m/$EVAL_TIMESTAMP" ] '
            '&& [ "$4" = m ] && [ "$5" = "$MODEL_TEST_BASE/shared/multimodal/benches" ]; then\n'
            '  printf "FAKE_SANITY\\n"; exit 0\n'
            'fi\nprintf "UNEXPECTED_PY_CALL\\n" >&2\nexit 98\n',
            encoding="utf-8",
        )
        fake_py.chmod(0o755)
        # Inherited BASH_ENV, credentials and SKIP_BENCHES never enter the child.
        self.env = {
            "PATH": "/usr/bin:/bin", "LC_ALL": "C",
            "MODEL_TEST_BASE": str(root), "PY": str(fake_py),
            "PYTHONDONTWRITEBYTECODE": "1", "EVAL_TIMESTAMP": "synthetic-session",
        }

    def run(self, skip=None, *, fail=None, shell_exports=None):
        env = dict(self.env)
        if skip is not None:
            env["SKIP_BENCHES"] = skip
        if fail is not None:
            env["FAKE_FAIL"] = fail
        argv = ["/bin/bash", str(self.script), "m", "http://fixture.invalid/v1"]
        if shell_exports is not None:
            argv = [
                "/bin/bash", "-c", 'eval "$1"; shift; exec "$@"',
                "loader-fixture", shell_exports, *argv,
            ]
        return subprocess.run(
            argv, cwd=self.root, env=env, capture_output=True, text=True, timeout=10,
        )


def selected_source():
    """SKIP_BENCHES_TEST_REVISION=HEAD makes C6.1 assert the contract against HEAD."""
    return source(os.environ.get("SKIP_BENCHES_TEST_REVISION") or None)
