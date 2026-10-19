"""Exercise real runner modules against a loopback-only synthetic server."""
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
import json
import os
import shutil
from pathlib import Path
import tempfile

from orchestration.smoke.cleanup import remove_base
from orchestration.smoke.configuration import TRACKS, configuration
from orchestration.smoke.execution import BOUNDS, run
from orchestration.smoke.isolation import assemble, environment
from orchestration.smoke.offline_server import start


@contextmanager
def fixture(root, host):
    target = Path(tempfile.mkdtemp(prefix="smoke-offline-fixture-", dir="/tmp"))
    try:
        for name in ("shared", "data", "configs", ".venv", ".venv-taubench"):
            (target / name).symlink_to(root / name, target_is_directory=True)
        models = target / "orchestration/models"
        models.mkdir(parents=True)
        for package in ("laneconf", "tracks"):
            shutil.copytree(root / "orchestration" / package, target / "orchestration" / package)
        tokenizer = target / "tokenizer"
        tokenizer.mkdir()
        (tokenizer / "chat_template.jinja").write_text("{% set enable_thinking = false %}")
        (models / "fixture.conf").write_text(
            f"CONFIG=qwen_qwen3.5_27b_fp8\nHOST_ENV=SMOKE_FIXTURE_HOST\nHOST_DEFAULT=invalid.invalid:1\n"
            f"KEYVAR=FIXTURE_KEY\nLANE_DISPLAY=fixture\nSESSION_KMMLU=fixture\nLANE_TOKENIZER={tokenizer}\n")
        (target / ".env").write_text("FIXTURE_KEY=synthetic-smoke-key\n")
        yield target
    finally:
        shutil.rmtree(target)


def scenario(root, server, fault, tracks=TRACKS, *, cleanup):
    base = assemble(root)
    # In-process dataset modules retain their first cache path between scenarios.
    # Keep every owned BASE until the entire exercise ends, including on failure.
    cleanup.callback(remove_base, base, root, created=base)
    stamp = datetime.now(timezone.utc).strftime("smoke_%Y%m%d_%H%M%S_%f")
    ctx = configuration(root, base, environment(root, base, stamp), stamp, "fixture")
    server.fault, server.calls = fault, []
    summary = run(ctx, tracks, before_track=lambda track: setattr(server, "track", track))
    for track in tracks:
        assert sum(t == track for t, _ in server.calls) <= BOUNDS[track], server.calls
    return summary


def verdict(summary, failed=None):
    for row in summary["tracks"]:
        expected = "FAIL" if row["track"] == failed else "PASS"
        assert row["status"] == expected, summary
        scope = "preflight" if row["track"] in ("harness", "taubench") else "full-run"
        assert row["scope"] == scope, row
    assert summary["rc"] == (1 if failed else 0), summary


def exercise_cases(root, server, cleanup):
    reports = []
    reports.append(scenario(root, server, None, cleanup=cleanup))
    verdict(reports[-1])
    print("PASS all five tracks; harness/taubench scope=preflight", flush=True)
    for kind in ("models", "chat"):
        for track in TRACKS:
            reports.append(scenario(root, server, (track, kind), cleanup=cleanup))
            verdict(reports[-1], track)
            print(f"PASS {track} {kind} corruption isolated", flush=True)
    template = root / "tokenizer/chat_template.jinja"
    template.unlink()
    summary = scenario(root, server, ("nlu", "models"), ("harness", "nlu"), cleanup=cleanup)
    assert [r["status"] for r in summary["tracks"]] == ["INCONCLUSIVE", "FAIL"], summary
    assert summary["rc"] == 1, summary
    reports.append(summary)
    summary = scenario(root, server, None, ("harness",), cleanup=cleanup)
    assert summary["rc"] == 77, summary
    reports.append(summary)
    print("PASS FAIL+INCONCLUSIVE=1; INCONCLUSIVE-only=77", flush=True)
    return reports


def exercise(root, server):
    """Release this test's bases only after all scenarios and artifact checks."""
    with ExitStack() as cleanup:
        reports = exercise_cases(root, server, cleanup)
    for report in reports:
        report['base_kept'] = False
    return reports


def main():
    root = Path(__file__).resolve().parents[2]
    try:
        server, thread = start("qwen_qwen3.5_27b_fp8", "synthetic-smoke-key")
    except OSError as exc:
        print(f"INCONCLUSIVE loopback bind: {exc}")
        return 77
    # Explicit HOST_ENV beats an intentionally unreachable HOST_DEFAULT in the test.
    previous = os.environ.get("SMOKE_FIXTURE_HOST")
    os.environ["SMOKE_FIXTURE_HOST"] = f"127.0.0.1:{server.server_port}"
    try:
        with fixture(root, f"127.0.0.1:{server.server_port}") as target:
            reports = exercise(target, server)
            print(json.dumps(reports, indent=2))
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
        if previous is None:
            os.environ.pop("SMOKE_FIXTURE_HOST", None)
        else:
            os.environ["SMOKE_FIXTURE_HOST"] = previous
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
