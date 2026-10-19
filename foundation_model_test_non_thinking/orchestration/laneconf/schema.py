"""The model-conf whitelist, shell destinations, and defaults live here."""
from dataclasses import dataclass

# Internal settings must not shadow commonly exported operating environments.
FORBIDDEN_VARIABLES = frozenset("""DISPLAY HOME PATH USER LOGNAME SHELL TERM LANG
LC_ALL TMPDIR PWD OLDPWD EDITOR PAGER SSH_AUTH_SOCK XDG_CACHE_HOME VIRTUAL_ENV""".split())


class ConfigError(ValueError):
    """A literal model configuration violates the lane contract."""


@dataclass(frozen=True)
class Setting:
    variable: str
    default: str = ""
    scoped: bool = True
    required: bool = False


SETTINGS = {
    "CONFIG": Setting("CONFIG", scoped=False, required=True),
    "HOST_ENV": Setting("HOST_ENV", scoped=False, required=True),
    "HOST_DEFAULT": Setting("HOST_DEFAULT", scoped=False, required=True),
    "KEYVAR": Setting("KEYVAR", scoped=False, required=True),
    "LANE_DISPLAY": Setting("LANE_DISPLAY", scoped=False, required=True),
    "LANE_TOKENIZER": Setting("LANE_TOKENIZER"),
    "REPS": Setting("REPS", "3"),
    "REQUIRE_NOTHINK": Setting("REQUIRE_NOTHINK", "1"),
    "LM_EVAL_MODE": Setting("LM_EVAL_MODE", "chat"),
    "NUM_CONCURRENT": Setting("NUM_CONCURRENT", "8"),
    "TAUBENCH_USER_MODEL": Setting("TAUBENCH_USER_MODEL", "openrouter/openai/gpt-4.1-mini"),
    "TAUBENCH_TRIALS": Setting("TAUBENCH_TRIALS", "4"),
    "TAUBENCH_MAX_CONCURRENCY": Setting("TAUBENCH_MAX_CONCURRENCY", "4"),
    "AGENT_REQUEST_TIMEOUT": Setting("AGENT_REQUEST_TIMEOUT", "300"),
    "AGENT_TASK_TIMEOUT": Setting("FULL_AGENT_TASK_TIMEOUT", "900"),
    "KRETA_WORKERS": Setting("FULL_KRETA_WORKERS", "4"),
    "KRETA_RESUME": Setting("FULL_KRETA_RESUME", "0"),
    "RESUME_FROM": Setting("FULL_RESUME_FROM"),
}


def key_table(tracks):
    """Extend the fixed settings with the supplied tracks' session keys."""
    sessions = {"SESSION_" + track.upper(): Setting("SESSION_" + track.upper(), scoped=False)
                for track in tracks}
    return {**SETTINGS, **sessions}
