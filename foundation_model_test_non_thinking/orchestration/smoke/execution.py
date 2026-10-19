"""Sequential runner execution, with bounded child process groups."""
import json
import subprocess
import time

from orchestration.smoke import artifacts, http_preflight
from orchestration.smoke.commands import command, prerequisites
from orchestration.smoke.isolation import Unavailable
from orchestration.smoke.processes import terminate

BOUNDS = {"harness": 2, "nlu": 2, "functionchat": 4, "taubench": 2, "multimodal": 4}


def record(ctx, track):
    return dict(track=track, scope="preflight" if track in ("harness", "taubench") else "full-run",
                model=ctx.model, endpoint=ctx.endpoint, status="INCONCLUSIVE", runner_rc=None,
                elapsed_seconds=0, request_upper_bound=BOUNDS[track], concurrency=1,
                checks=[], artifacts=[], timeout=False)


def invoke(ctx, track, argv, result):
    proc = subprocess.Popen(argv, cwd=ctx.base, env=ctx.env, start_new_session=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        output, _ = proc.communicate(timeout={"nlu": 620, "functionchat": 155, "multimodal": 150}[track])
    except subprocess.TimeoutExpired:
        output, _ = terminate(proc)
        result["timeout"] = True
    except KeyboardInterrupt:
        terminate(proc)
        raise
    result["runner_rc"] = proc.returncode
    output = output.replace(ctx.env["OPENAI_API_KEY"], "<redacted>")
    (ctx.base / "logs/smoke" / ctx.stamp / (track + ".runner.log")).write_text(output)
    if track == "functionchat" and ("timeout" in output.lower() or "timed out" in output.lower()):
        result["timeout"] = True
    if track == "functionchat":
        directory = artifacts.result_dir(ctx, "language/functionchat")
        for name in ("singlecall", "call_decision", "dialog"):
            path = directory / (name + ".json")
            if path.is_file():
                for item in artifacts.read(path).get("results", []):
                    error = str(item.get("error") or "").lower()
                    result["timeout"] |= "timeout" in error or "timed out" in error
    if any(text in output for text in ("ModuleNotFoundError:", "패키지 미설치", "OfflineModeIsEnabled", "Couldn't find cache")):
        raise Unavailable("runner dependency/offline cache unavailable; see runner log")
    artifacts.require(not result["timeout"], "runner timeout; later tracks will not start")
    return proc.returncode


def execute(ctx, track):
    started = time.monotonic()
    result = record(ctx, track)
    try:
        prerequisites(ctx, track)
        argv = command(ctx, track) if result["scope"] == "full-run" else None
        result["checks"].append("inputs_available")
        if track != "functionchat":  # functionchat already checks /models itself.
            http_preflight.models(ctx)
            result["checks"].append("model_list")
        if track == "harness":
            template = (ctx.tokenizer / "chat_template.jinja").read_text()
            artifacts.require("set enable_thinking = false" in template, "non-thinking template absent")
            result["checks"].append("non_thinking_template")
        if argv is None:
            http_preflight.chat(ctx)
            result["checks"].append("one_token_chat")
            result["runner_rc"] = 0
        else:
            rc = invoke(ctx, track, argv, result)
            paths = getattr(artifacts, track)(ctx, rc)
            result["artifacts"] = [str(path.relative_to(ctx.base)) for path in paths]
            result["checks"].append("runner_artifacts")
        result["status"] = "PASS"
    except Unavailable as exc:
        result.update(status="INCONCLUSIVE", reason=str(exc))
    except Exception as exc:
        reason = str(exc).replace(ctx.env["OPENAI_API_KEY"], "<redacted>")
        result.update(status="FAIL", reason=f"{type(exc).__name__}: {reason}")
    result["elapsed_seconds"] = round(time.monotonic() - started, 3)
    return result


def aggregate(results):
    statuses = {result["status"] for result in results}
    return 1 if "FAIL" in statuses else 77 if "INCONCLUSIVE" in statuses else 0


def run(ctx, tracks, before_track=None):
    directory = ctx.base / "logs/smoke" / ctx.stamp
    directory.mkdir(parents=True)
    results, blocked = [], False
    for track in tracks:
        if blocked:
            result = record(ctx, track)
            result["reason"] = "previous functionchat timeout; outstanding server work cannot be ruled out"
        else:
            if before_track:
                before_track(track)
            result = execute(ctx, track)
        blocked = blocked or (track == "functionchat" and result["timeout"])
        (directory / (track + ".json")).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        results.append(result)
    return dict(base=str(ctx.base), timestamp=ctx.stamp, rc=aggregate(results), tracks=results)
