"""Read literal model conf and .env values; reuse the existing config exporter."""
from dataclasses import dataclass
import os
from pathlib import Path
import re
import shlex
import subprocess

from .isolation import Unavailable

TRACKS = ("harness", "nlu", "functionchat", "taubench", "multimodal")


@dataclass
class Context:
    root: Path
    base: Path
    env: dict
    stamp: str
    model: str
    endpoint: str
    tokenizer: Path


def literals(path):
    values = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        if not sep or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise ValueError(f"invalid assignment in {path.name}")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values.setdefault(key, value)
    return values


def configuration(root, base, env, stamp, name):
    if not re.fullmatch(r"[a-z0-9_]+", name):
        raise ValueError("invalid model_conf: use [a-z0-9_] only")
    conf = literals(root / "orchestration/models" / (name + ".conf"))
    for key in ("HOST_ENV", "KEYVAR"):
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", conf[key]):
            raise ValueError(f"invalid {key}")
    host = os.environ.get(conf["HOST_ENV"]) or conf["HOST_DEFAULT"]
    if not re.fullmatch(r"[A-Za-z0-9.\[\]:_-]+", host):
        raise ValueError("HOST must be an endpoint host[:port], without path or credentials")
    endpoint = f"http://{host}/v1"
    key = read_key(root / ".env", conf["KEYVAR"])
    if not key:
        raise Unavailable(f"missing .env key: {conf['KEYVAR']}")
    env.update(OPENAI_API_KEY=key, BASE_URL_V1_OVERRIDE=endpoint,
               BASE_URL_CHAT_OVERRIDE=endpoint + "/chat/completions")
    command = [str(base / ".venv/bin/python"), "-B",
               str(root / "configs/load_model_config.py"), conf["CONFIG"]]
    proc = subprocess.run(command, env=env, cwd=base, capture_output=True, text=True)
    if proc.returncode:
        raise Unavailable("model config loader failed")
    for line in proc.stdout.splitlines():
        words = shlex.split(line)
        if len(words) != 2 or words[0] not in ("export", "unset"):
            raise ValueError("unexpected model config exporter output")
        if words[0] == "unset":
            env.pop(words[1], None)
        else:
            key, value = words[1].split("=", 1)
            env[key] = value
    tok = conf.get("KMMLU_LANE_TOKENIZER", conf.get("LANE_TOKENIZER", ""))
    return Context(root, base, env, stamp, env["MODEL"], endpoint, Path(tok))


def read_key(path, name):
    # Other .env entries need not follow model-conf grammar. Never source/eval.
    for line in path.read_text().splitlines():
        if line.startswith(name + "="):
            value = line.split("=", 1)[1].strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            return value
    return ""
