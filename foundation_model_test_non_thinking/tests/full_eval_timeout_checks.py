#!/usr/bin/env python3
"""Exercise a copied full-eval driver using only temporary, fake track scripts.

Usage: python3 -I tests/full_eval_timeout_checks.py [--case NAME] [TARGET]
No lanes, guards, datasets or servers are invoked. Times/PIDs are not compared.
"""
import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile


REPO = Path(__file__).resolve().parents[1]
REQUEST = "AGENT_REQUEST_TIMEOUT"
TASK = "AGENT_TASK_TIMEOUT"
REQUEST_ERROR = "AGENT_REQUEST_TIMEOUT must be a positive integer"
TASK_ERROR = "AGENT_TASK_TIMEOUT must be an integer greater than AGENT_REQUEST_TIMEOUT"
TRACKS = ("harness", "functionchat", "nlu", "taubench", "multimodal", "agent")
CASES = ("defaults", "override", "request_only", "task_only", "empty",
         "isolation", "invalid", "logs", "agent")

TRACK_SCRIPT = '''import json, os, pathlib, sys
keys = ("AGENT_REQUEST_TIMEOUT", "AGENT_TASK_TIMEOUT",
        "FULL_EVAL_REQUEST_TIMEOUT", "FULL_EVAL_TASK_TIMEOUT")
record = {"track": sys.argv[1], "env": {key: os.environ[key] for key in keys if key in os.environ}}
with pathlib.Path(os.environ["CASE"], "calls.jsonl").open("a") as stream:
    stream.write(json.dumps(record) + "\\n")
'''


def write(path, content, executable=False):
    """Create fixture files beneath the supplied temporary root."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    if executable:
        path.chmod(0o755)


def fixture(base, target, overrides, tracks):
    """Copy the driver/helper and provide every external evaluation dependency."""
    shutil.copy2(target, base / "run_full_eval.sh")
    helper = target.parent / "shared/harness/harness_lib.sh"
    destination = base / "shared/harness/harness_lib.sh"
    destination.parent.mkdir(parents=True)
    shutil.copy2(helper, destination)
    write(base / ".venv/bin/activate", 'touch "$CASE/activated"\n')
    write(base / ".env", 'touch "$CASE/keys_read"\nexport OPENAI_API_KEY=fixture-only\n')
    config = {"MODEL": "fixture-model", "TOKENIZER": "fixture-tokenizer",
              "MODEL_CLASS": "fixture", "BASE_URL_CHAT": "http://fixture.invalid/v1/chat/completions",
              "BASE_URL_V1": "http://fixture.invalid/v1", "TRACKS": " ".join(tracks)}
    assignments = "\n".join(f"export {key}={shlex.quote(value)}" for key, value in config.items())
    write(base / "configs/load_model_config.py", f"print({assignments!r})\n")
    write(base / "bin/curl", '#!/bin/bash\ntouch "$CASE/preflight"\n'
          'printf \'%s\\n\' \'{"data":[{"id":"fixture-model"}]}\'\n', True)
    python = shlex.quote(sys.executable)
    for name in ("python", "python3"):
        write(base / f"bin/{name}", f'#!/bin/bash\nexec {python} -I "$@"\n', True)
    write(base / "track.py", TRACK_SCRIPT)
    for name in TRACKS:
        script = {"multimodal": "run_all.sh", "agent": "run_gpustack_custom.sh"}.get(
            name, f"run_{name}.sh")
        write(base / "fixture" / name / script,
              f'#!/bin/bash\nexec {python} -I "$CASE/track.py" {name}\n', True)
    for directory in ("tmp", "early_logs", "home"):
        (base / directory).mkdir()
    env = {"PATH": str(base / "bin") + os.pathsep + os.defpath, "LC_ALL": "C",
           "HOME": str(base / "home"), "TMPDIR": str(base / "tmp"), "CASE": str(base),
           "OPENAI_API_KEY": "fixture-only", "EVAL_TIMESTAMP": "fixture_session",
           "PYTHONDONTWRITEBYTECODE": "1", "_FULL_EVAL_REEXEC": "1",
           "LOG_DIR": str(base / "early_logs")}
    env.update(overrides)
    return env


def execute(target, overrides, tracks, verify):
    """Run only the temporary copy, then verify it before automatic cleanup."""
    with tempfile.TemporaryDirectory(prefix="full_eval_timeout_", dir="/tmp") as directory:
        base = Path(directory)
        env = fixture(base, target, overrides, tracks)
        result = subprocess.run(["/bin/bash", str(base / "run_full_eval.sh"), "fixture"],
                                env=env, cwd=base, capture_output=True, text=True, timeout=30)
        calls_path = base / "calls.jsonl"
        calls = [json.loads(line) for line in calls_path.read_text().splitlines()] if calls_path.exists() else []
        verify(base, result, calls)


def verify_valid(base, result, calls, pair, tracks):
    """Check executed environments as well as the master log and command arguments."""
    assert result.returncode == 0, f"driver rc={result.returncode}: {result.stderr}"
    expected_tracks = [name for name in tracks if name != "agent"]
    assert [call["track"] for call in calls] == expected_tracks, f"executed tracks: {calls}"
    consumers = {call["track"]: call["env"] for call in calls
                 if call["track"] in ("functionchat", "taubench")}
    expected = {REQUEST: pair[0], TASK: pair[1]}
    assert consumers == {name: expected for name in ("functionchat", "taubench")}, (
        f"both fake tracks executed; timeout mismatch: expected {expected}, observed {consumers}")
    for call in calls:
        if call["track"] not in consumers:
            assert call["env"] == {}, f"timeout leaked to {call}"
    for marker in ("activated", "keys_read", "preflight"):
        assert (base / marker).exists(), f"fixture did not reach {marker}"
    if "agent" in tracks:
        assert "WARN: unknown track 'agent'" in result.stdout, result.stdout
    master = (base / "logs/fixture_session/_master.log").read_text()
    header = (f"[full_eval] {REQUEST}={pair[0]} {TASK}={pair[1]} "
              "(functionchat·taubench only)")
    assert master.splitlines().count(header) == 1, f"missing/duplicate timeout header: {master}"
    assert master.index("[full_eval] EVAL_TIMESTAMP=") < master.index(header) < master.index(" 시작 ===")
    commands = [line for line in master.splitlines() if line.startswith("  CMD: ")]
    assert len(commands) == len(expected_tracks), commands
    for name, command in zip(expected_tracks, commands):
        if name in consumers:
            assert command.startswith(f"  CMD: env {REQUEST}={pair[0]} {TASK}={pair[1]} bash "), command
        else:
            assert REQUEST not in command and TASK not in command, command


def valid_case(target, name):
    """Exercise defaults, overrides and isolation with fixed expected values."""
    overrides, pair = {
        "defaults": ({}, ("300", "900")),
        "override": ({REQUEST: "350", TASK: "1000"}, ("350", "1000")),
        "request_only": ({REQUEST: "350"}, ("350", "900")),
        "task_only": ({TASK: "1000"}, ("300", "1000")),
        "empty": ({REQUEST: "", TASK: ""}, ("300", "900")),
        "isolation": ({REQUEST: "350", TASK: "1000",
                       "FULL_EVAL_REQUEST_TIMEOUT": "1", "FULL_EVAL_TASK_TIMEOUT": "2"}, ("350", "1000")),
        "logs": ({REQUEST: "350", TASK: "1000"}, ("350", "1000")),
        "agent": ({}, ("300", "900")),
    }[name]
    tracks = TRACKS + ("harness", "nlu") if name == "isolation" else TRACKS
    execute(target, overrides, tracks,
            lambda base, result, calls: verify_valid(base, result, calls, pair, tracks))


def verify_invalid(base, result, calls, message):
    """Reject configuration before activation, secrets, HTTP or any track."""
    assert result.returncode == 2, f"expected rc 2, got {result.returncode}: {result.stdout} {result.stderr}"
    expected = f"[full_eval] ERROR: {message}"
    assert result.stderr.splitlines() == [expected], f"wrong stderr: {result.stderr!r}"
    assert not calls, f"tracks ran on invalid input: {calls}"
    for marker in ("activated", "keys_read", "preflight", "logs"):
        assert not (base / marker).exists(), f"invalid input reached {marker}"


def invalid_case(target):
    """Cover each invalid input class and both TASK <= REQUEST boundaries."""
    pairs = [({key: value}, message) for key, message in
             ((REQUEST, REQUEST_ERROR), (TASK, TASK_ERROR))
             for value in ("0", "-1", "1.5", "x")]
    pairs += [({REQUEST: "300", TASK: "300"}, TASK_ERROR),
              ({REQUEST: "300", TASK: "299"}, TASK_ERROR),
              ({REQUEST: "900"}, TASK_ERROR)]
    for overrides, message in pairs:
        try:
            execute(target, overrides, TRACKS,
                    lambda base, result, calls: verify_invalid(base, result, calls, message))
        except AssertionError as exc:
            raise AssertionError(f"{overrides}: {exc}") from exc


def main(argv=None):
    """Select cases and return nonzero only when an assertion/setup fails."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=CASES)
    parser.add_argument("target", type=Path, nargs="?", default=REPO / "run_full_eval.sh")
    args = parser.parse_args(argv)
    target = args.target.resolve()
    if not target.is_file() or not (target.parent / "shared/harness/harness_lib.sh").is_file():
        parser.error("target and adjacent shared/harness/harness_lib.sh are required")
    failures = 0
    for name in (args.case,) if args.case else CASES:
        try:
            if name == "invalid":
                invalid_case(target)
            else:
                valid_case(target, name)
        except (AssertionError, OSError, subprocess.TimeoutExpired) as exc:
            print(f"FAIL {name}: {exc}", flush=True)
            failures += 1
        else:
            print(f"PASS {name}", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
