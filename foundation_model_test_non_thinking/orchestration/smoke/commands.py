"""Existing runner invocations and read-only prerequisite checks."""
import subprocess

from .isolation import Unavailable, copy_cache


def files(paths):
    for path in paths:
        if not path.is_file():
            raise Unavailable(f"required input missing: {path}")


def prerequisites(ctx, track):
    if track in ("nlu", "functionchat", "multimodal"):
        dependencies(ctx, track)
    if track == "harness":
        files([ctx.tokenizer / "chat_template.jinja"])
    elif track == "nlu":
        files([ctx.root / "shared/nlu/prompt/carwash.yaml", ctx.root / "shared/nlu/contract.json"])
    elif track == "taubench":
        bench = ctx.base / "data/tau2-bench"
        files([ctx.base / ".venv-taubench/bin/python", bench / "src/tau2/cli.py"])
        proc = subprocess.run(["git", "-C", str(bench), "rev-parse", "HEAD"],
                              capture_output=True, text=True, env=ctx.env)
        if proc.returncode or proc.stdout.strip() != "c3398666e6559e3a063da3fc04b5acf7f941464e":
            raise Unavailable("tau2-bench pinned commit unavailable")
    elif track == "functionchat":
        directory = ctx.base / "data/FunctionChat-Bench/data"
        files([directory / f"FunctionChat-{name}.jsonl" for name in ("Singlecall", "CallDecision", "Dialog")])
        files([directory / "system_prompt.txt"])
        files([ctx.base / "data/Ko-AgentBench/bench" / name
               for name in ("adapters/base_adapter.py", "observability.py")])


def dependencies(ctx, track):
    modules = {"nlu": ["requests"], "functionchat": ["openai"],
               "multimodal": ["openai", "datasets", "PIL"]}[track]
    code = "import importlib.util as u; import sys; sys.exit(any(u.find_spec(m) is None for m in sys.argv[1:]))"
    argv = [str(ctx.base / ".venv/bin/python"), "-B", "-c", code] + modules
    proc = subprocess.run(argv, env=ctx.env, cwd=ctx.base, capture_output=True)
    if proc.returncode:
        raise Unavailable(f"{track} Python dependencies unavailable: {','.join(modules)}")
    if track == "multimodal":
        # The approved HTTP upper bound includes at most two SDK retries.
        code = "from openai._constants import DEFAULT_MAX_RETRIES; assert DEFAULT_MAX_RETRIES <= 2"
        proc = subprocess.run(argv[:3] + [code], env=ctx.env, cwd=ctx.base, capture_output=True)
        if proc.returncode:
            raise Unavailable("OpenAI SDK retry default exceeds approved request bound")


def command(ctx, track):
    prefix = [str(ctx.base / ".venv/bin/python"), "-B", "-m"]
    identity = ["--model", ctx.model]
    if track == "nlu":
        return prefix + ["shared.nlu.nlu_gpustack"] + identity + [
            "--endpoint", ctx.endpoint + "/chat/completions", "--prompt",
            str(ctx.root / "shared/nlu/prompt/carwash.yaml")]
    if track == "functionchat":
        return prefix + ["shared.functionchat.runner.run_functionchat"] + identity + [
            "--base-url", ctx.endpoint + "/chat/completions", "--track-name", "functionchat",
            "--limit", "1", "--request-timeout", "30", "--task-timeout", "45",
            "--max-retries", "1", "--max-tokens", "256"]
    revision = copy_cache(ctx.base)
    return prefix + ["shared.multimodal.benches.k_dtcbench"] + identity + [
        "--base-url", ctx.endpoint, "--limit", "1", "--max-tokens", "32",
        "--timeout", "30", "--retry-max", "1", "--revision", revision]
