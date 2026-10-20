"""Pure scope resolution and the common lane validation contract."""
import re

from orchestration.laneconf.schema import ConfigError, key_table


def scoped_key(key, tracks):
    """Identify a session or the longest supplied track prefix."""
    if key != "LANE_DISPLAY" and not key.startswith("SESSION_"):
        for track in sorted(tracks, key=lambda item: (-len(item), item)):
            prefix = track.upper() + "_"
            if key.startswith(prefix):
                return track, key[len(prefix):]
    return None, key


def resolve(entries, track, tracks, require_session=True):
    """Validate every entry, then apply defaults, common, and selected scope."""
    tracks = tuple(tracks)
    if track not in tracks:
        raise ConfigError(f"unknown TRACK: {track}")
    table = key_table(tracks)
    result = {setting.variable: setting.default for setting in table.values()}
    scoped = []
    for original, value in entries:
        scope, key = scoped_key(original, tracks)
        if key == "DISPLAY":
            raise ConfigError("key renamed: DISPLAY -> LANE_DISPLAY")
        if key not in table:
            raise ConfigError(f"unknown key: {key}")
        setting = table[key]
        if scope is not None and not setting.scoped:
            raise ConfigError(f"key cannot have track prefix: {key}")
        scoped.append((scope, setting.variable, value))
    for selected in (None, track):
        for scope, variable, value in scoped:
            if scope == selected:
                result[variable] = value
    for key, setting in table.items():
        if setting.required and not result[setting.variable]:
            raise ConfigError(f"required key: {key}")
    session_key = "SESSION_" + track.upper()
    result["SESSION"] = result[session_key]
    if require_session and not result["SESSION"]:
        raise ConfigError(f"required key: {session_key}")
    names = result["HOST_ENV"] + ":" + result["KEYVAR"]
    # Preserve Bash's original case pattern, including its colon allowance.
    if re.search(r"[^a-zA-Z0-9_:]|^[0-9]|:[0-9]", names):
        raise ConfigError("invalid environment variable name")
    return result
